// Explicit wired-AND for Verilator; physical top uses an actual tristate pad.
module sim_top (
    input logic clk, rst, scl, master_low,
    input logic signed [13:0] i_sample, q_sample,
    input logic valid, chirp_start, chirp_end,
    output wire sda,
    output logic done, error
);
    logic sda_low;
    logic [12:0] byte_address;
    logic [7:0] read_data;
    assign sda = ~(master_low | sda_low);
    capture_store store(.*);
    capture_i2c transport(.sda_in(sda),.*);
endmodule
