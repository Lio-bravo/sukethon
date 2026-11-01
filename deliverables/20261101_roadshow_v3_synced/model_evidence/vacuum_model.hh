#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <stdexcept>

// Gauge vacuum magnitude in Pa (ambient minus absolute pressure).
// Lumped, isothermal engineering approximation; parameters require hardware calibration.
struct VacuumModel {
  double tank=0, overloadTime=0;
  std::array<double,4> pressure{{0,0,0,0}};
  std::array<double,4> seal{{0,0,0,0}};
  double force=0, shearCapacity=0, peelCapacity=0;
  bool fault=false;
  static constexpr double ambient=101325, pumpLimit=65000;
  static constexpr double radius=.034, efficiency=.80, friction=.55, safety=1.30;
  static constexpr double tankLiters=2.0, cupLiters=.025, pumpLitersPerSecond=5.0;
  void reset() { *this=VacuumModel(); }
  void step(double dt, bool enabled, double leak=0) {
    if(!std::isfinite(dt)||dt<0||!std::isfinite(leak)||leak<0) throw std::invalid_argument("Invalid vacuum step");
    // Substeps keep the pressure network stable at variable simulator timesteps.
    while(dt>1e-12) {
      double h=std::min(dt,.001); dt-=h;
      double tankFlow=pumpLitersPerSecond*(pumpLimit-tank);
      for(int i=0;i<4;++i) {
        double q=enabled ? .12*(tank-pressure[i]) : 0;
        double leakage=.00015+.45*(1-std::max(0.0,std::min(1.0,seal[i])))+leak;
        double vent=enabled ? leakage : 1.0;
        pressure[i]=std::max(0.0,std::min(double(ambient),pressure[i]+h*(q-vent*pressure[i])/cupLiters));
        tankFlow-=q;
      }
      tank=std::max(0.0,std::min(double(pumpLimit),tank+h*tankFlow/tankLiters));
    }
    force=0;
    for(int i=0;i<4;++i) force+=pressure[i]*3.141592653589793*radius*radius*efficiency*seal[i];
    shearCapacity=force*friction;
    peelCapacity=force*.055*.5;
  }
  bool ready() const {
    int cups=0; for(int i=0;i<4;++i) if(seal[i]>.95 && pressure[i]>=35000) ++cups;
    return cups>=3 && force>=180 && !fault;
  }
  bool evaluate(double dt,double normal,double shear,double moment) {
    if(!std::isfinite(normal)||!std::isfinite(shear)||!std::isfinite(moment)) {fault=true;return true;}
    bool over=normal*safety>force || shear*safety>shearCapacity || moment*safety>peelCapacity;
    overloadTime=over ? overloadTime+dt : 0;
    if(overloadTime>=.04) fault=true;
    return fault;
  }
};
