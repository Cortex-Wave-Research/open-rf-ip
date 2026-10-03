// Simulation-only explicit wired AND; actual pad is in high_purity_capture_top.
module hp_capture_sim (
    input logic clk, rst, scl, master_low,
    input logic signed [17:0] i_sample, q_sample,
    input logic valid, chirp_start, chirp_end,
    output wire sda,
    output logic done, error
);
    logic sda_low;
    logic [12:0] byte_address;
    logic [7:0] read_data;
    assign sda = ~(master_low | sda_low);
    hp_capture_store store(.*);
    capture_i2c transport(.sda_in(sda),.*);
endmodule
