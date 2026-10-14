// Protocol assertions for the owned DBusSimple-to-Wishbone adapter.
module openrf_dbus_wishbone_formal (
    input logic clk, rst, cmd_valid, cmd_wr,
    input logic [31:0] cmd_address, cmd_data,
    input logic [3:0] cmd_mask,
    input logic wb_ack, wb_err,
    input logic [31:0] wb_rdata,
    output logic [5:0] reached
);
    logic cmd_ready, rsp_ready, rsp_error, fault;
    logic wb_cyc, wb_stb, wb_we;
    logic [31:0] rsp_data, wb_wdata;
    logic [15:0] wb_addr;
    logic [3:0] wb_sel;
    openrf_dbus_wishbone dut(.*);

    logic past_valid = 0;
    logic [5:0] seen = 0;
    logic [52:0] expected_command;
    logic expected_write, expected_error;
    logic [31:0] expected_response;
    assign reached = seen;

    // The frozen Wishbone slave also qualifies ACK/ERR with CYC and STB.
    always_ff @(posedge clk) begin
        past_valid <= 1;
        if (!past_valid) assume(rst);
        if (!wb_cyc || !wb_stb) assume(!wb_ack && !wb_err);

        if (rst) begin
            seen <= 0;
        end else if (past_valid) begin
            assert(wb_cyc == wb_stb);
            assume(!(wb_ack && wb_err));
            if (wb_ack || wb_err) assert(wb_cyc && wb_stb);

            // A command captured in IDLE must be the single subsequent
            // Wishbone request, with byte address truncated as designed.
            if (wb_cyc && wb_stb) begin
                assert(wb_cyc && wb_stb);
                assert({wb_we,wb_addr,wb_wdata,wb_sel} == expected_command);
                seen[0] <= 1;
            end

            // REARM is entered only after a Wishbone ACK/ERR. Write response
            // data remains unspecified and is intentionally not compared.
            if (!wb_cyc && !cmd_ready) begin
                assert(rsp_ready == !expected_write);
                assert(rsp_error == expected_error);
                assert(fault == expected_error);
                if (!expected_error && !expected_write)
                    assert(rsp_data == expected_response);
                if (expected_error) assert(rsp_data == 0);
                seen[1] <= 1;
                if (expected_write) seen[3] <= 1;
                else seen[4] <= 1;
                if (expected_error) seen[5] <= 1;
            end

            if (wb_cyc && wb_stb && wb_ack && !wb_err) seen[2] <= 1;

            if (cmd_valid && cmd_ready) begin
                expected_command <= {cmd_wr,cmd_address[15:0],cmd_data,cmd_mask};
                expected_write <= cmd_wr;
                seen[0] <= 1;
            end
            if (wb_cyc && wb_stb && (wb_ack || wb_err)) begin
                expected_error <= wb_err;
                expected_response <= wb_err ? 32'd0 : wb_rdata;
            end
        end
    end
endmodule
