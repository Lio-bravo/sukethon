#include "vacuum_model.hh"
#include <cassert>
#include <iostream>
int main() {
 VacuumModel v;
 for(int n=0;n<3000;++n) v.step(.001,true);
 assert(!v.ready() && v.force==0); // Unsealed cups never acquire a load.
 v.seal.fill(1);
 for(int n=0;n<2000;++n) v.step(.001,true);
 assert(v.ready() && v.force>600 && v.force<800);
 for(int n=0;n<100;++n) assert(!v.evaluate(.001,98.1,10,1));
 for(int n=0;n<50;++n) v.evaluate(.001,1000,0,0);
 assert(v.fault);
 v.reset();v.seal.fill(1);
 for(int n=0;n<3000;++n) v.step(.001,true);
 for(int n=0;n<1000;++n) v.step(.001,true,.5);
 assert(v.force<180 && !v.ready());
 v.reset();v.seal.fill(1);
 for(int n=0;n<3000;++n) v.step(.001,true);
 for(int n=0;n<400;++n) v.step(.001,false);
 assert(v.force<.01);
 v.reset();v.seal={{1,1,0,0}};
 for(int n=0;n<3000;++n) v.step(.001,true);
 assert(!v.ready());
 bool invalid=false;try { v.step(-1,true); } catch(const std::invalid_argument&) { invalid=true; }
 assert(invalid);
 v.reset();v.seal.fill(1);
 for(int n=0;n<3000;++n) v.step(.001,true);
 for(int n=0;n<50;++n) v.evaluate(.001,50,1000,0);
 assert(v.fault);
 v.reset();v.seal.fill(1);
 for(int n=0;n<3000;++n) v.step(.001,true);
 for(int n=0;n<50;++n) v.evaluate(.001,50,0,1000);
 assert(v.fault);
 std::cout << "PASS: no seal, acquisition, normal load, overload, leak, vent, two-cup rejection, invalid input, shear and peel trip\n";
}
