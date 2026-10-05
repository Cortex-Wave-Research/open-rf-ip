// Offline feasibility harness. Dynamic registered bus inputs retain all runtime
// configuration logic. A 55-bit shift chain supplies unconstrained dynamic bus
// values without a pin-heavy parallel bus. No serial protocol or host bridge is
// implemented. Parity retains I/Q and bus response; not a board demonstration.
module control_plane_top #(
    parameter integer HIGH_PURITY=0, ENGINE_KIND=1
) (
    input logic clk,
    input logic serial_in,
    input logic reset_in,
    output logic activity
);
    logic [54:0] bus_registered;
    logic wb_rst_i;
    always_ff @(posedge clk) begin
        bus_registered <= {bus_registered[53:0],serial_in};
        wb_rst_i <= reset_in;
    end
    wire wb_cyc_i=bus_registered[54];
    wire wb_stb_i=bus_registered[53];
    wire wb_we_i=bus_registered[52];
    wire [3:0] wb_sel_i=bus_registered[51:48];
    wire [15:0] wb_adr_i=bus_registered[47:32];
    wire [31:0] wb_dat_i=bus_registered[31:0];
    logic [31:0] wb_dat_o;
    logic wb_ack_o, wb_err_o, sample_valid, chirp_start, chirp_end;
    localparam integer B=HIGH_PURITY != 0 ? 18 : 14;
    logic signed [B-1:0] i_out,q_out;
    if (ENGINE_KIND != 0) begin : chirp
        openrf_controlled_chirp #(.HIGH_PURITY(HIGH_PURITY)) controlled (.wb_clk_i(clk),.*);
    end else begin : tone
        openrf_controlled_nco #(.HIGH_PURITY(HIGH_PURITY)) controlled (.wb_clk_i(clk),.*);
    end
    always_ff @(posedge clk)
        activity <= ^{wb_dat_o,wb_ack_o,wb_err_o,i_out,q_out,sample_valid,chirp_start,chirp_end};
endmodule
