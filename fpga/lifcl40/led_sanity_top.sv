// Board-only test: native 12 MHz, no reset, PLL, ROM or DSP.
module led_sanity_top (
    input  logic clk,
    output logic led0_n,
    output logic led1_n
);
    // Configuration initializes the registers. Count 3,000,000 input edges
    // per quarter-second; the two-bit phase counter wraps modulo four.
    logic [21:0] count = 22'd0;
    logic [1:0] blink_phase = 2'd0;
    always_ff @(posedge clk) begin
        if (count == 22'd2999999) begin
            count <= 22'd0;
            blink_phase <= blink_phase + 2'd1;
        end else begin
            count <= count + 22'd1;
        end
    end
    // Schematic Figure A.7: cathodes at FPGA pins, anodes via 2k to VCCIO1.
    assign led0_n = ~blink_phase[1]; // 0.5 s per state: 1 Hz full cycle.
    assign led1_n = ~blink_phase[0]; // 0.25 s per state: 2 Hz full cycle.
endmodule
