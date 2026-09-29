#include "Vnative_clock_test_top.h"
#include "Vnative_clock_test_top___024root.h"
#include <cstdio>
int main() {
    Vnative_clock_test_top top;
    top.clk_12mhz = 0; top.eval();
    if (top.led0 != 1 || top.led1 != 1) return 1;
    for (unsigned edge=1; edge<=16777232U; ++edge) {
        top.clk_12mhz=1; top.eval();
        unsigned expected=edge & 0xffffffU;
        if (top.rootp->native_clock_test_top__DOT__counter != expected ||
            top.led0 != (1U ^ ((edge / 8388608U) & 1U)) ||
            top.led1 != (1U ^ ((edge / 4194304U) & 1U))) return 2;
        top.clk_12mhz=0; top.eval();
        if (top.rootp->native_clock_test_top__DOT__counter != expected) return 3;
        // No new edge must leave both state and LED outputs unchanged.
        unsigned l0=top.led0, l1=top.led1;
        top.eval();
        if (top.led0 != l0 || top.led1 != l1) return 4;
    }
    top.final();
    std::puts("PASS: 16777232 edges, every count/LED checked, divider boundaries, wrap, falling-edge and stopped-clock hold");
}
