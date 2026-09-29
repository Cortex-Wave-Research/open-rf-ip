// Board-only native clock proof: binary division, no reset or clock gating.
module native_clock_test_top (
    input logic clk_12mhz,
    output logic led0,
    output logic led1
);
    logic [23:0] counter /* verilator public_flat_rd */ = 24'd0;
    always_ff @(posedge clk_12mhz) counter <= counter + 24'd1;
    assign led0 = ~counter[23]; // 12 MHz / 2^24 = 0.7152557373 Hz
    assign led1 = ~counter[22]; // 12 MHz / 2^23 = 1.4305114746 Hz
endmodule
