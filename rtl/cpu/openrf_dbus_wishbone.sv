// One owned DBusSimple command, one Wishbone Classic transaction.
// Address decoding precedes this adapter; low 16 bits are BYTE offsets.
module openrf_dbus_wishbone (
    input logic clk, rst,
    input logic cmd_valid, cmd_wr,
    input logic [31:0] cmd_address, cmd_data,
    input logic [3:0] cmd_mask,
    output logic cmd_ready,
    output logic rsp_ready, rsp_error,
    output logic [31:0] rsp_data,
    output logic fault,
    output logic wb_cyc, wb_stb, wb_we,
    output logic [15:0] wb_addr,
    output logic [31:0] wb_wdata,
    output logic [3:0] wb_sel,
    input logic wb_ack, wb_err,
    input logic [31:0] wb_rdata
);
    typedef enum logic [1:0] {IDLE, WAIT_RESPONSE, REARM} state_t;
    state_t state;
    wire [15:0] unused_decoded_region = cmd_address[31:16];
    assign cmd_ready = state == IDLE && !rst;
    assign wb_cyc = state == WAIT_RESPONSE && !rst;
    assign wb_stb = wb_cyc;
    always_ff @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            wb_we <= 1'b0; wb_addr <= 16'd0; wb_wdata <= 32'd0; wb_sel <= 4'd0;
            rsp_ready <= 1'b0; rsp_error <= 1'b0; rsp_data <= 32'd0; fault <= 1'b0;
        end else begin
            rsp_ready <= 1'b0; rsp_error <= 1'b0; fault <= 1'b0;
            case (state)
                IDLE: if (cmd_valid) begin
                    wb_we <= cmd_wr; wb_addr <= cmd_address[15:0];
                    wb_wdata <= cmd_data; wb_sel <= cmd_mask;
                    state <= WAIT_RESPONSE;
                end
                WAIT_RESPONSE: if (wb_ack || wb_err) begin
                    rsp_ready <= !wb_we; rsp_error <= wb_err;
                    rsp_data <= wb_err ? 32'd0 : wb_rdata;
                    fault <= wb_err;
                    state <= REARM;
                end
                REARM: state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
