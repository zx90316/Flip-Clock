// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "FlipProtocol.h"
namespace flip {
// Explicit UART-only bench mode. Any I2C master activity locks it until reset.
class BenchGate {
 public:
  bool enabled=false,masterSeen=false;
  bool enable(const Endpoint& e) {
    if(masterSeen || e.armed || e.state==RUNNING) return false;
    enabled=true; return true;
  }
  void disable(Endpoint& e) {
    if(enabled && (e.armed || e.state==RUNNING)) e.fail(INTERNAL_FAULT);
    enabled=false;
  }
  void masterActivity(Endpoint& e) { disable(e); masterSeen=true; }
  bool submit(const Frame& f,Endpoint& e,uint32_t now) {
    if(!enabled || masterSeen || !f.valid()) return false;
    if(f.op()==ARM && (f.arg(0)>50 || f.arg(1)>10000UL)) return false;
    if(f.op()==MOVE && (f.steps()<1 || f.steps()>256 || f.arg(1)>50 || f.arg(3)>10000UL)) return false;
    e.handle(f,now); return true;
  }
};
} // namespace flip
