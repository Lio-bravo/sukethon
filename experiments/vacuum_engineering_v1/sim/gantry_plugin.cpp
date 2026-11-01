#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo/sensors/sensors.hh>
#include <ros/ros.h>
#include <std_msgs/Float64MultiArray.h>
#include <std_msgs/Bool.h>
#include <std_msgs/String.h>
#include <sensor_msgs/JointState.h>
#include <fstream>
#include <cstdlib>
#include <iomanip>
#include <sstream>
#include <mutex>
#include <array>
#include "vacuum_model.hh"

namespace gazebo {
class Gantry : public ModelPlugin {
  physics::ModelPtr model;
  physics::JointPtr attachment;
  sensors::ContactSensorPtr contact;
  event::ConnectionPtr update;
  std::unique_ptr<ros::NodeHandle> node;
  ros::Subscriber command, vacuum;
  ros::Publisher feedback, joints, telemetry;
  std::ofstream telemetryFile;
  bool lastAttached=false, lastContact=false;
  transport::NodePtr visualNode;
  transport::PublisherPtr silkPublisher;
  std::mutex mutex;
  std::array<double,4> target{{0,0,2.5,0}};
  bool enabled=false;
  double last=0;
  std::array<double,4> integral{{0,0,0,0}};
  double previousStep=-1;
  VacuumModel pneumatic;
  physics::LinkPtr payload;
  ignition::math::Vector3d previousVelocity;
  ignition::math::Vector3d acceleration;
  double normalDemand=0, shearDemand=0, momentDemand=0, leak=0;
  double attachedSince=-1;
  std::string failureReason="none";
  std::string faultMode;
  void detach(const std::string &reason) {
    if(attachment) { attachment->Detach(); attachment->Fini(); attachment.reset(); }
    payload.reset(); failureReason=reason;
  }
public:
  void Load(physics::ModelPtr m, sdf::ElementPtr) override {
    if (!ros::isInitialized()) { gzerr << "ROS gazebo API plugin required\n"; return; }
    model=m;
    if(const char *f=std::getenv("SUKETHON_VACUUM_FAULT")) faultMode=f;
    visualNode.reset(new transport::Node());
    visualNode->Init(model->GetWorld()->Name());
    silkPublisher=visualNode->Advertise<msgs::Visual>("~/visual");
    node.reset(new ros::NodeHandle("/gantry"));
    command=node->subscribe<std_msgs::Float64MultiArray>("target",1,[this](const std_msgs::Float64MultiArray::ConstPtr &msg){
      if(msg->data.size()!=4) return;
      for(auto v:msg->data) if(!std::isfinite(v)) return;
      if(std::abs(msg->data[0])>2 || std::abs(msg->data[1])>2 || msg->data[2]<0.6 || msg->data[2]>2.8) return;
      std::lock_guard<std::mutex> lock(mutex);
      std::copy(msg->data.begin(),msg->data.end(),target.begin());
    });
    vacuum=node->subscribe<std_msgs::Bool>("vacuum",1,[this](const std_msgs::Bool::ConstPtr &msg){
      std::lock_guard<std::mutex> lock(mutex); enabled=msg->data;
    });
    feedback=node->advertise<std_msgs::Bool>("attached",1);
    joints=node->advertise<sensor_msgs::JointState>("joint_states",1);
    telemetry=node->advertise<std_msgs::String>("telemetry",1);
    if(const char *path=std::getenv("SUKETHON_TELEMETRY")) telemetryFile.open(path,std::ios::out|std::ios::trunc);
    update=event::Events::ConnectWorldUpdateBegin(std::bind(&Gantry::Step,this));
  }
  void Step() {
    std::lock_guard<std::mutex> lock(mutex);
    // Force-actuated axes: positions of boxes are never read for planning or attachment.
    const char *names[]={"axis_x","axis_y","axis_z","axis_yaw"};
    const double kp[]={3500,3500,5000,120}, kd[]={100,100,160,8}, limit[]={1800,1800,2200,150};
    double simulationTime=model->GetWorld()->SimTime().Double();
    if(previousStep>=0 && simulationTime<previousStep) {
      last=simulationTime-.03;
      integral.fill(0);
      enabled=false;
      detach("reset"); pneumatic.reset(); attachedSince=-1;
      target={{0,0,2.1,0}};
    }
    double dt=previousStep<0 ? 0 : std::max(0.0,std::min(.01,simulationTime-previousStep));
    previousStep=simulationTime;
    sensor_msgs::JointState state;
    state.header.stamp=ros::Time(simulationTime);
    for(int i=0;i<4;++i) {
      auto joint=model->GetJoint(names[i]);
      double q=joint->Position(0)+(i==2 ? 2.1 : 0.0), v=joint->GetVelocity(0);
      double error=target[i]-q;
      const double integralLimit=i==3 ? .25 : .06;
      const double integralGain=i==3 ? 1500 : 5000;
      integral[i]=std::max(-integralLimit,std::min(integralLimit,integral[i]+error*dt));
      double force=kp[i]*error-kd[i]*v+integralGain*integral[i];
      force=std::max(-limit[i],std::min(limit[i],force));
      joint->SetForce(0,force);
      state.name.push_back(names[i]); state.position.push_back(q); state.velocity.push_back(v); state.effort.push_back(force);
    }
    if(!contact) {
      for(auto sensor:sensors::SensorManager::Instance()->GetSensors())
        if(sensor->Name().find("vacuum_contact")!=std::string::npos) {
          contact=std::dynamic_pointer_cast<sensors::ContactSensor>(sensor);
          if(contact) { contact->SetActive(true); gzmsg << "Vacuum contact sensor ready: " << sensor->Name() << "\n"; }
        }
    }
    if(!enabled) {
      pneumatic.fault=false; pneumatic.overloadTime=0;
    }
    physics::LinkPtr candidate=payload;
    if(!candidate && enabled && contact && !pneumatic.fault) {
      auto contacts=contact->Contacts();
      for(int i=0;i<contacts.contact_size();++i) {
        auto c=contacts.contact(i);
        auto name=c.collision1().find("box_")==0 ? c.collision1():c.collision2();
        if(name.find("box_")!=0) continue;
        auto collision=boost::dynamic_pointer_cast<physics::Collision>(model->GetWorld()->EntityByName(name));
        if(collision) { candidate=collision->GetLink(); break; }
      }
    }
    pneumatic.seal.fill(0);
    auto tool=model->GetLink("tool");
    if(candidate) {
      auto pose=candidate->WorldPose();
      auto collisions=candidate->GetCollisions();
      auto shape=collisions.empty() ? physics::BoxShapePtr() : boost::dynamic_pointer_cast<physics::BoxShape>(collisions[0]->GetShape());
      if(shape) {
        auto size=shape->Size(); int i=0;
        for(double x:{-.075,.075}) for(double y:{-.055,.055}) {
          auto world=tool->WorldPose().Pos()+tool->WorldPose().Rot().RotateVector(ignition::math::Vector3d(x,y,-.060));
          auto local=pose.Rot().RotateVectorReverse(world-pose.Pos());
          double edge=std::min(size.X()/2-std::abs(local.X()),size.Y()/2-std::abs(local.Y()));
          double gap=std::abs(local.Z()-size.Z()/2);
          double alignment=tool->WorldPose().Rot().RotateVector(ignition::math::Vector3d(0,0,1)).Dot(pose.Rot().RotateVector(ignition::math::Vector3d(0,0,1)));
          if(gap<.018 && alignment>std::cos(.12)) pneumatic.seal[i]=std::max(0.0,std::min(1.0,(edge-.020)/.014));
          ++i;
        }
      }
    }
    leak=(faultMode=="leak" && attachment && simulationTime-attachedSince>2) ? .5 : 0;
    pneumatic.step(dt,enabled,leak);
    double maxPressure=*std::max_element(pneumatic.pressure.begin(),pneumatic.pressure.end());
    if(!enabled && attachment && maxPressure<3000) detach("commanded_vent");
    if(enabled && !attachment && candidate && pneumatic.ready()) {
      attachment=model->GetWorld()->Physics()->CreateJoint("fixed",model);
      attachment->Load(tool,candidate,ignition::math::Pose3d()); attachment->Init();
      payload=candidate; attachedSince=simulationTime; previousVelocity=payload->WorldLinearVel();
      acceleration.Set(0,0,0); failureReason="none";
    }
    normalDemand=shearDemand=momentDemand=0;
    if(attachment && payload) {
      auto velocity=payload->WorldLinearVel();
      if(dt>0) acceleration=.9*acceleration+.1*((velocity-previousVelocity)/dt);
      previousVelocity=velocity;
      double mass=payload->GetInertial()->Mass();
      // Load demand uses simulated mass and acceleration, not commanded motor effort.
      auto load=mass*(acceleration-model->GetWorld()->Gravity());
      auto local=tool->WorldPose().Rot().RotateVectorReverse(load);
      normalDemand=std::max(0.0,local.Z()); shearDemand=std::hypot(local.X(),local.Y());
      auto moment=(payload->WorldCoGPose().Pos()-tool->WorldPose().Pos()).Cross(load);
      auto localMoment=tool->WorldPose().Rot().RotateVectorReverse(moment);
      momentDemand=std::hypot(localMoment.X(),localMoment.Y());
      // Deliberately injected demand, distinct from physical box mass, for protective-trip testing.
      if(faultMode=="overload" && simulationTime-attachedSince>2) normalDemand+=1000;
      if(enabled && pneumatic.evaluate(dt,normalDemand,shearDemand,momentDemand)) detach(leak>0 ? "leak_capacity_loss" : "load_capacity_exceeded");
    }
    double now=model->GetWorld()->SimTime().Double();
    if(now-last>0.02) {
      // Cosmetic silk retracts between the measured tool height and the spinneret.
      const double toolHeight=model->GetJoint("axis_z")->Position(0)+2.1;
      const double silkLength=4.71-toolHeight;
      msgs::Visual silk;
      silk.set_name(model->GetScopedName()+"::slide_z::spider_silk");
      silk.set_parent_name(model->GetScopedName()+"::slide_z");
      msgs::Set(silk.mutable_pose(),ignition::math::Pose3d(0,0,.06+silkLength/2,0,0,0));
      auto box=silk.mutable_geometry(); box->set_type(msgs::Geometry::BOX);
      msgs::Set(box->mutable_box()->mutable_size(),ignition::math::Vector3d(.012,.012,silkLength));
      silkPublisher->Publish(silk);
      std_msgs::Bool status; status.data=bool(attachment); feedback.publish(status); joints.publish(state);
      std::ostringstream line; line << std::fixed << std::setprecision(6)
        << "{\"t\":" << now << ",\"stream\":\"gantry\",\"kind\":\"measured\",\"vacuum_enabled\":" << (enabled?"true":"false")
        << ",\"attached\":" << (attachment?"true":"false") << ",\"contact\":" << ((contact && contact->Contacts().contact_size()>0)?"true":"false")
        << ",\"tank_vacuum_pa\":" << pneumatic.tank << ",\"suction_capacity_n\":" << pneumatic.force
        << ",\"normal_demand_n\":" << normalDemand << ",\"shear_demand_n\":" << shearDemand
        << ",\"peel_moment_nm\":" << momentDemand << ",\"shear_capacity_n\":" << pneumatic.shearCapacity
        << ",\"peel_capacity_nm\":" << pneumatic.peelCapacity << ",\"vacuum_fault\":" << (pneumatic.fault?"true":"false")
        << ",\"detach_reason\":\"" << failureReason << "\",\"cup_vacuum_pa\":[";
      for(int i=0;i<4;++i) line << (i?",":"") << pneumatic.pressure[i];
      line << "],\"cup_seal\":["; for(int i=0;i<4;++i) line << (i?",":"") << pneumatic.seal[i];
      line << "],\"names\":[\"axis_x\",\"axis_y\",\"axis_z\",\"axis_yaw\"],\"target\":[";
      for(int i=0;i<4;++i) line << (i?",":"") << target[i];
      line << "],\"position\":["; for(int i=0;i<4;++i) line << (i?",":"") << state.position[i];
      line << "],\"velocity\":["; for(int i=0;i<4;++i) line << (i?",":"") << state.velocity[i];
      line << "],\"effort\":["; for(int i=0;i<4;++i) line << (i?",":"") << state.effort[i]; line << "]}";
      std_msgs::String telemetryMsg; telemetryMsg.data=line.str(); telemetry.publish(telemetryMsg);
      if(telemetryFile.is_open()) { telemetryFile << line.str() << '\n'; telemetryFile.flush(); }
      last=now;
    }
  }
};
GZ_REGISTER_MODEL_PLUGIN(Gantry)
}
