// Separate optional instrument-control demonstration; production IP is unchanged.
module openrf_vexriscv_system #(
    parameter integer HIGH_PURITY=0, ENGINE_KIND=1,
    parameter ROM_FILE="build/vexriscv/firmware/firmware.hex"
) (
    input logic clk, rst,
    output logic signed [17:0] i_out, q_out,
    output logic sample_valid, chirp_start, chirp_end,
    output logic [31:0] mailbox_o,
    output logic bus_fault
);
    logic i_valid, i_ready, i_rsp_valid, i_error;
    logic [31:0] i_pc, i_inst;
    logic d_valid, d_ready, d_wr, d_rsp_ready, d_error;
    logic [31:0] d_address, d_data, d_rdata;
    logic [3:0] d_mask;
    logic [1:0] d_size;
    logic wb_cyc, wb_stb, wb_we, wb_ack, wb_err;
    logic [15:0] wb_addr;
    logic [31:0] wb_wdata, wb_rdata;
    logic [3:0] wb_sel;
    VexRiscv cpu (
        .clk(clk),.reset(rst),.iBus_cmd_valid(i_valid),.iBus_cmd_ready(i_ready),
        .iBus_cmd_payload_pc(i_pc),.iBus_rsp_valid(i_rsp_valid),
        .iBus_rsp_payload_error(i_error),.iBus_rsp_payload_inst(i_inst),
        .dBus_cmd_valid(d_valid),.dBus_cmd_ready(d_ready),.dBus_cmd_payload_wr(d_wr),
        .dBus_cmd_payload_address(d_address),.dBus_cmd_payload_data(d_data),
        .dBus_cmd_payload_mask(d_mask),.dBus_cmd_payload_size(d_size),
        .dBus_rsp_ready(d_rsp_ready),.dBus_rsp_error(d_error),.dBus_rsp_data(d_rdata));
    openrf_cpu_memory #(.ROM_FILE(ROM_FILE)) memory_bus (.*);
    localparam integer OW = HIGH_PURITY != 0 ? 18 : 14;
    wire signed [OW-1:0] wave_i, wave_q;
    assign i_out = 18'($signed(wave_i));
    assign q_out = 18'($signed(wave_q));
    if (ENGINE_KIND == 0) begin : tone
        openrf_controlled_nco #(.HIGH_PURITY(HIGH_PURITY)) controlled (
            .wb_clk_i(clk),.wb_rst_i(rst),.wb_cyc_i(wb_cyc),.wb_stb_i(wb_stb),
            .wb_we_i(wb_we),.wb_adr_i(wb_addr),.wb_dat_i(wb_wdata),.wb_sel_i(wb_sel),
            .wb_dat_o(wb_rdata),.wb_ack_o(wb_ack),.wb_err_o(wb_err),
            .i_out(wave_i),.q_out(wave_q),.sample_valid(sample_valid),
            .chirp_start(chirp_start),.chirp_end(chirp_end));
    end else begin : chirp
        openrf_controlled_chirp #(.HIGH_PURITY(HIGH_PURITY)) controlled (
            .wb_clk_i(clk),.wb_rst_i(rst),.wb_cyc_i(wb_cyc),.wb_stb_i(wb_stb),
            .wb_we_i(wb_we),.wb_adr_i(wb_addr),.wb_dat_i(wb_wdata),.wb_sel_i(wb_sel),
            .wb_dat_o(wb_rdata),.wb_ack_o(wb_ack),.wb_err_o(wb_err),
            .i_out(wave_i),.q_out(wave_q),.sample_valid(sample_valid),
            .chirp_start(chirp_start),.chirp_end(chirp_end));
    end
endmodule
