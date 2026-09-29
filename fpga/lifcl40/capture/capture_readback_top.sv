module capture_readback_top (
    input logic clk_12mhz,
    input logic scl,
    inout wire sda,
    output logic led0, led1
);
    logic [3:0] startup = 4'b1111;
    always_ff @(posedge clk_12mhz) startup <= {startup[2:0],1'b0};
    logic signed [13:0] i_sample, q_sample;
    logic valid, chirp_start, chirp_end, unused_busy;
    logic [31:0] unused_inc, unused_count;
    logic [12:0] byte_address;
    logic [7:0] read_data;
    logic done, error, sda_low;
    assign sda = sda_low ? 1'b0 : 1'bz;
    assign led0 = ~done;
    assign led1 = ~error;
    rf_chirp_nco chirp (
        .clk(clk_12mhz),.rst(startup[3]),.enable(1'b1),.start(1'b1),
        .start_phase_inc(32'd178956971),.chirp_step(32'sd53692),
        .chirp_length(32'd10000),.repeat_mode(1'b0),
        .i_out(i_sample),.q_out(q_sample),.sample_valid(valid),
        .chirp_start(chirp_start),.chirp_end(chirp_end),.busy(unused_busy),
        .phase_increment(unused_inc),.chirp_count(unused_count)
    );
    capture_store store(.clk(clk_12mhz),.rst(startup[3]),.*);
    capture_i2c transport(.clk(clk_12mhz),.rst(startup[3]),.sda_in(sda),.*);
endmodule
