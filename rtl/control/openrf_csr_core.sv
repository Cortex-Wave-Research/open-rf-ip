// Protocol-independent: one transaction per clk rising edge with req_i asserted.
// Combinational read/error; atomic state transition. Same clock as waveform RTL.
module openrf_csr_core #(
    parameter integer HIGH_PURITY = 0,
    parameter integer ENGINE_KIND = 1 // 0=tone only; 1=chirp only
) (
    input logic clk, rst, req_i, we_i,
    input logic [15:0] addr_i,
    input logic [31:0] wdata_i,
    input logic [3:0] sel_i,
    output logic [31:0] rdata_o,
    output logic error_o,
    input logic engine_busy_i, engine_done_i,
    output logic start_o, run_enable_o, config_valid_o,
    output logic [63:0] active_nco_o, active_start_o,
    output logic signed [63:0] active_step_o,
    output logic [31:0] active_length_o,
    output logic active_repeat_o
);
    logic [31:0] scratch, errors, sequence_number;
    logic dirty, done_sticky;
    logic [31:0] shadow [0:8];
    logic [31:0] byte_mask, command_errors;
    logic invalid_config, command_write, clear_status, busy;
    localparam logic [31:0] CAPS = (HIGH_PURITY != 0 ? openrf_control_pkg::CAP_HIGH_PURITY : openrf_control_pkg::CAP_COMPACT) |
        (ENGINE_KIND != 0 ? (openrf_control_pkg::CAP_CHIRP | openrf_control_pkg::CAP_REPEAT) : openrf_control_pkg::CAP_TONE) | openrf_control_pkg::CAP_PAUSE;
    if ((HIGH_PURITY != 0 && HIGH_PURITY != 1) ||
        (ENGINE_KIND != 0 && ENGINE_KIND != 1)) begin : invalid_parameters
        initial $fatal(1, "control supports two purity profiles and tone/chirp builds");
    end
    assign byte_mask = {{8{sel_i[3]}},{8{sel_i[2]}},{8{sel_i[1]}},{8{sel_i[0]}}};
    assign busy = engine_busy_i || start_o;
    assign invalid_config = shadow[0] != (ENGINE_KIND != 0 ? openrf_control_pkg::MODE_CHIRP : openrf_control_pkg::MODE_TONE) ||
        (shadow[8] & 32'hfffffffe) != 0 ||
        (ENGINE_KIND != 0 && shadow[7] == 0) ||
        (HIGH_PURITY == 0 && (shadow[2] != 0 || shadow[4] != 0 ||
         shadow[6] != {32{shadow[5][31]}}));
    assign command_write = req_i && we_i && !error_o && addr_i == openrf_control_pkg::ADDR_COMMAND;
    assign clear_status = command_write && sel_i == 4'hf && wdata_i == openrf_control_pkg::CMD_CLEAR_STATUS;
    always_comb begin
        command_errors = 32'd0;
        if (command_write) begin
            if (sel_i != 4'hf) command_errors = openrf_control_pkg::ERR_BAD_COMMAND;
            else case (wdata_i)
                openrf_control_pkg::CMD_COMMIT: begin
                    if (busy) command_errors = command_errors | openrf_control_pkg::ERR_COMMIT_WHILE_BUSY;
                    if (invalid_config) command_errors = command_errors | openrf_control_pkg::ERR_INVALID_CONFIGURATION;
                end
                openrf_control_pkg::CMD_START: begin
                    if (ENGINE_KIND == 0) command_errors = command_errors | openrf_control_pkg::ERR_BAD_COMMAND;
                    if (busy) command_errors = command_errors | openrf_control_pkg::ERR_START_WHILE_BUSY;
                    if (dirty) command_errors = command_errors | openrf_control_pkg::ERR_START_WITH_DIRTY_CONFIG;
                    if (!config_valid_o) command_errors = command_errors | openrf_control_pkg::ERR_START_WITHOUT_VALID_CONFIG;
                    if (!run_enable_o) command_errors = command_errors | openrf_control_pkg::ERR_START_WHILE_DISABLED;
                end
                openrf_control_pkg::CMD_CLEAR_STATUS: command_errors = 32'd0;
                default: command_errors = openrf_control_pkg::ERR_BAD_COMMAND;
            endcase
        end
    end
    always_comb begin
        rdata_o = 32'd0;
        error_o = 1'b0;
        case (addr_i)
            openrf_control_pkg::ADDR_IP_ID: begin rdata_o = openrf_control_pkg::IP_ID_VALUE; error_o = we_i; end
            openrf_control_pkg::ADDR_ABI_VERSION: begin rdata_o = openrf_control_pkg::ABI_VERSION_VALUE; error_o = we_i; end
            openrf_control_pkg::ADDR_CAPABILITIES: begin rdata_o = CAPS; error_o = we_i; end
            openrf_control_pkg::ADDR_SCRATCH: rdata_o = scratch;
            openrf_control_pkg::ADDR_COMMAND: rdata_o = 32'd0;
            openrf_control_pkg::ADDR_STATUS: begin
                rdata_o = (run_enable_o ? openrf_control_pkg::STATUS_RUN_ENABLE : 32'd0) |
                    (config_valid_o ? openrf_control_pkg::STATUS_CONFIG_VALID : 32'd0) |
                    (dirty ? openrf_control_pkg::STATUS_CONFIG_DIRTY : 32'd0) |
                    ((|errors) ? openrf_control_pkg::STATUS_ERROR_STICKY : 32'd0) |
                    (done_sticky ? openrf_control_pkg::STATUS_DONE_STICKY : 32'd0) |
                    (busy ? openrf_control_pkg::STATUS_BUSY : 32'd0);
                error_o = we_i;
            end
            openrf_control_pkg::ADDR_ERROR_STATUS: begin rdata_o = errors; error_o = we_i; end
            openrf_control_pkg::ADDR_CONFIG_SEQUENCE: begin rdata_o = sequence_number; error_o = we_i; end
            openrf_control_pkg::ADDR_RUN_CONTROL: begin
                rdata_o = {31'd0,run_enable_o};
                if (we_i && (wdata_i & byte_mask & 32'hfffffffe) != 0) error_o = 1'b1;
            end
            openrf_control_pkg::ADDR_MODE: rdata_o = shadow[0];
            openrf_control_pkg::ADDR_NCO_PHASE_INC_LO: rdata_o = shadow[1];
            openrf_control_pkg::ADDR_NCO_PHASE_INC_HI: rdata_o = shadow[2];
            openrf_control_pkg::ADDR_CHIRP_START_LO: rdata_o = shadow[3];
            openrf_control_pkg::ADDR_CHIRP_START_HI: rdata_o = shadow[4];
            openrf_control_pkg::ADDR_CHIRP_STEP_LO: rdata_o = shadow[5];
            openrf_control_pkg::ADDR_CHIRP_STEP_HI: rdata_o = shadow[6];
            openrf_control_pkg::ADDR_CHIRP_LENGTH: rdata_o = shadow[7];
            openrf_control_pkg::ADDR_CHIRP_CONFIG: rdata_o = shadow[8];
            default: error_o = 1'b1; // includes every misaligned byte address
        endcase
    end
    always_ff @(posedge clk) begin
        if (rst) begin
            scratch <= 32'd0; errors <= 32'd0; sequence_number <= 32'd0;
            dirty <= 1'b0; done_sticky <= 1'b0; config_valid_o <= 1'b0;
            run_enable_o <= 1'b0; start_o <= 1'b0;
            active_nco_o <= 64'd0; active_start_o <= 64'd0; active_step_o <= 64'sd0;
            active_length_o <= 32'd0; active_repeat_o <= 1'b0;
            for (integer k=0;k<9;k=k+1) shadow[k] <= 32'd0;
            shadow[0] <= 32'(ENGINE_KIND);
        end else begin
            start_o <= 1'b0;
            if (clear_status) begin errors <= 32'd0; done_sticky <= 1'b0; end
            else errors <= errors | command_errors | ((req_i && error_o) ? openrf_control_pkg::ERR_ILLEGAL_BUS_ACCESS : 32'd0);
            // A real completion on the clear edge wins: events cannot be lost.
            if (engine_done_i && ENGINE_KIND != 0) done_sticky <= 1'b1;
            if (command_write && command_errors == 0) begin
                if (wdata_i == openrf_control_pkg::CMD_COMMIT) begin
                    active_nco_o <= {shadow[2],shadow[1]};
                    active_start_o <= {shadow[4],shadow[3]};
                    active_step_o <= $signed({shadow[6],shadow[5]});
                    active_length_o <= shadow[7]; active_repeat_o <= shadow[8][0];
                    dirty <= 1'b0; config_valid_o <= 1'b1;
                    sequence_number <= 32'(sequence_number + 32'd1);
                end
                if (wdata_i == openrf_control_pkg::CMD_START) start_o <= 1'b1;
            end
            if (req_i && we_i && !error_o) begin
                case (addr_i)
                    openrf_control_pkg::ADDR_SCRATCH: scratch <= (scratch & ~byte_mask) | (wdata_i & byte_mask);
                    openrf_control_pkg::ADDR_RUN_CONTROL: if (sel_i[0]) run_enable_o <= wdata_i[0];
                    openrf_control_pkg::ADDR_MODE: begin
                        shadow[0] <= (shadow[0] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_NCO_PHASE_INC_LO: begin
                        shadow[1] <= (shadow[1] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_NCO_PHASE_INC_HI: begin
                        shadow[2] <= (shadow[2] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_START_LO: begin
                        shadow[3] <= (shadow[3] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_START_HI: begin
                        shadow[4] <= (shadow[4] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_STEP_LO: begin
                        shadow[5] <= (shadow[5] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_STEP_HI: begin
                        shadow[6] <= (shadow[6] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_LENGTH: begin
                        shadow[7] <= (shadow[7] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    openrf_control_pkg::ADDR_CHIRP_CONFIG: begin
                        shadow[8] <= (shadow[8] & ~byte_mask) | (wdata_i & byte_mask);
                        dirty <= 1'b1;
                    end
                    default: begin end
                endcase
            end
        end
    end
endmodule
