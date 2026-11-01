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
public:
  void Load(physics::ModelPtr m, sdf::ElementPtr) override {
    if (!ros::isInitialized()) { gzerr << "ROS gazebo API plugin required\n"; return; }
    model=m;
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
      if(attachment) { attachment->Detach(); attachment->Fini(); attachment.reset(); }
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
    if(!enabled && attachment) { attachment->Detach(); attachment->Fini(); attachment.reset(); }
    // Simplified vacuum: fixed constraint can be created ONLY from contact sensor evidence.
    // This is not a pressure/peeling/overload model and must not be claimed as one.
    if(enabled && !attachment && contact) {
      auto contacts=contact->Contacts();
      static double lastContactLog=0;
      if(contacts.contact_size()>0 && model->GetWorld()->SimTime().Double()-lastContactLog>1) {
        gzmsg << "Vacuum contacts: " << contacts.contact(0).collision1() << " / " << contacts.contact(0).collision2() << "\n";
        lastContactLog=model->GetWorld()->SimTime().Double();
      }
      for(int i=0;i<contacts.contact_size();++i) {
        auto c=contacts.contact(i);
        auto name=c.collision1().find("box_")==0 ? c.collision1():c.collision2();
        if(name.find("box_")!=0) continue;
        auto entity=model->GetWorld()->EntityByName(name);
        auto collision=boost::dynamic_pointer_cast<physics::Collision>(entity);
        if(!collision) continue;
        attachment=model->GetWorld()->Physics()->CreateJoint("fixed",model);
        attachment->Load(model->GetLink("tool"),collision->GetLink(),ignition::math::Pose3d());
        attachment->Init(); break;
      }
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
        << ",\"names\":[\"axis_x\",\"axis_y\",\"axis_z\",\"axis_yaw\"],\"target\":[";
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
