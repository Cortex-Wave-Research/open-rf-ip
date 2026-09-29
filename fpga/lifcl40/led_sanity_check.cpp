// Check real divider periods for two seconds of nominal 12 MHz input edges.
#include "Vled_sanity_top.h"
#include <cstdio>
int main() {
    Vled_sanity_top top;
    top.clk = 0; top.eval();
    if (top.led0_n != 1 || top.led1_n != 1) return 1;
    for (unsigned edge = 1; edge <= 24000000; ++edge) {
        top.clk = 1; top.eval();
        const unsigned led0 = 1U ^ ((edge / 6000000U) & 1U);
        const unsigned led1 = 1U ^ ((edge / 3000000U) & 1U);
        if (top.led0_n != led0 || top.led1_n != led1) {
            std::fprintf(stderr, "LED mismatch at edge %u\n", edge);
            return 1;
        }
        top.clk = 0; top.eval();
    }
    top.final();
    std::puts("PASS: 24,000,000 edges; initial off; LED0 1 Hz / LED1 2 Hz; zero mismatches");
}
