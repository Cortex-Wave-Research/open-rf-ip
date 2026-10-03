// Prepared 12 MHz physical validation; no automatic programming.
module high_purity_capture_top (
    input logic clk_12mhz, scl,
    inout wire sda,
    output logic led0, led1
);
    logic [3:0] startup = 4'b1111;
    always_ff @(posedge clk_12mhz) startup <= {startup[2:0],1'b0};
    logic signed [17:0] i_sample, q_sample;
    logic valid, chirp_start, chirp_end, unused_busy;
    logic [63:0] unused_inc;
    logic [31:0] unused_count;
    logic [12:0] byte_address;
    logic [7:0] read_data;
    logic done, error, sda_low;
    assign sda = sda_low ? 1'b0 : 1'bz;
    assign led0 = ~done;
    assign led1 = ~error;
    // Rationally rounded by models.python.high_purity.linear_config:
    // 500 kHz -> 2 MHz at 12 MHz, 10000 samples, 64-bit words.
    rf_chirp_nco_mode #(.HIGH_PURITY(1)) chirp (
        .clk(clk_12mhz),.rst(startup[3]),.enable(1'b1),.start(1'b1),
        .start_phase_inc(64'd768614336404564651),.chirp_step(64'sd230607361657535),
        .chirp_length(32'd10000),.repeat_mode(1'b0),
        .i_out(i_sample),.q_out(q_sample),.sample_valid(valid),
        .chirp_start(chirp_start),.chirp_end(chirp_end),.busy(unused_busy),
        .phase_increment(unused_inc),.chirp_count(unused_count));
    hp_capture_store store(.clk(clk_12mhz),.rst(startup[3]),.*);
    capture_i2c transport(.clk(clk_12mhz),.rst(startup[3]),.sda_in(sda),.*);
endmodule
