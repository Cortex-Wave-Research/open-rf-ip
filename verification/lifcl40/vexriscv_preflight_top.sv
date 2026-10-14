// Offline device-fit wrapper; its pins are synthetic and are not an operational
// board interface. The low I/Q bits keep the numerical datapath observable.
module vexriscv_preflight_top #(
    parameter integer HIGH_PURITY=0,
    parameter integer ENGINE_KIND=1
) (
    input logic clk,
    input logic reset_in,
    output logic [2:0] status
);
    logic signed [17:0] i_out, q_out;
    logic sample_valid, chirp_start, chirp_end;
    logic [31:0] mailbox_o;
    logic bus_fault;
    openrf_vexriscv_system #(
        .HIGH_PURITY(HIGH_PURITY), .ENGINE_KIND(ENGINE_KIND)
    ) system (
        .clk(clk), .rst(reset_in), .i_out(i_out), .q_out(q_out),
        .sample_valid(sample_valid), .chirp_start(chirp_start),
        .chirp_end(chirp_end), .mailbox_o(mailbox_o), .bus_fault(bus_fault)
    );
    assign status = {sample_valid, i_out[0], q_out[0] ^ bus_fault};
endmodule
