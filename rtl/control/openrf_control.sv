// Reusable composition of bus adapter and protocol-independent CSR semantics.
module openrf_control #(
    parameter integer HIGH_PURITY=0, ENGINE_KIND=1
) (
    input logic wb_clk_i, wb_rst_i, wb_cyc_i, wb_stb_i, wb_we_i,
    input logic [15:0] wb_adr_i,
    input logic [31:0] wb_dat_i,
    input logic [3:0] wb_sel_i,
    output logic [31:0] wb_dat_o,
    output logic wb_ack_o, wb_err_o,
    input logic engine_busy_i, engine_done_i,
    output logic start_o, run_enable_o, config_valid_o,
    output logic [63:0] active_nco_o, active_start_o,
    output logic signed [63:0] active_step_o,
    output logic [31:0] active_length_o,
    output logic active_repeat_o
);
    logic req, we, error;
    logic [15:0] addr;
    logic [31:0] wdata, rdata;
    logic [3:0] sel;
    openrf_wb_slave bus_adapter (.*,.req_o(req),.we_o(we),.addr_o(addr),
        .wdata_o(wdata),.sel_o(sel),.rdata_i(rdata),.error_i(error));
    openrf_csr_core #(.HIGH_PURITY(HIGH_PURITY),.ENGINE_KIND(ENGINE_KIND)) csr (
        .clk(wb_clk_i),.rst(wb_rst_i),.req_i(req),.we_i(we),.addr_i(addr),
        .wdata_i(wdata),.sel_i(sel),.rdata_o(rdata),.error_o(error),.*);
endmodule
