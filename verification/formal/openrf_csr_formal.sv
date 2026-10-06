// Architectural assertions; observations are connected to existing state by the
// proof script AFTER elaboration. No production source or driver is modified.
module openrf_csr_formal #(
    parameter integer HIGH_PURITY=0, ENGINE_KIND=1
)(input clk, rst, req_i, we_i, input [15:0] addr_i,
  input [31:0] wdata_i, input [3:0] sel_i,
  input engine_busy_i, engine_done_i,
  output [11:0] reached);
    wire [31:0] rdata_o;
    wire error_o, start_o, run_enable_o, config_valid_o;
    wire [63:0] active_nco_o, active_start_o, active_step_o;
    wire [31:0] active_length_o;
    wire active_repeat_o;
    openrf_csr_core #(.HIGH_PURITY(HIGH_PURITY),.ENGINE_KIND(ENGINE_KIND)) dut(.*);
    (* keep *) wire [31:0] s0,s1,s2,s3,s4,s5,s6,s7,s8,errors,sequence_number;
    (* keep *) wire dirty,done_sticky;
    wire [287:0] shadow = {s8,s7,s6,s5,s4,s3,s2,s1,s0};
    wire [224:0] active = {active_repeat_o,active_length_o,active_step_o,active_start_o,active_nco_o};
    wire [224:0] candidate = {s8[0],s7,s6,s5,s4,s3,s2,s1};
    wire shadow_write = req_i && we_i && addr_i[1:0]==0 &&
        (addr_i==16'h20 || (addr_i>=16'h28 && addr_i<=16'h44));
    wire good_config = s0==ENGINE_KIND && s8<=1 && (ENGINE_KIND==0 || s7!=0) &&
        (HIGH_PURITY!=0 || (s2==0 && s4==0 &&
          ($signed({s6,s5}) >= -64'sd2147483648 && $signed({s6,s5}) <= 64'sd2147483647)));
    wire command = req_i && we_i && addr_i==16'h10;
    wire commit = command && sel_i==15 && wdata_i==1;
    wire launch = command && sel_i==15 && wdata_i==2;
    wire clear = command && sel_i==15 && wdata_i==4;
    wire busy = engine_busy_i || start_o;
    wire accepted = commit && !busy && good_config;
    wire start_ok = launch && ENGINE_KIND!=0 && !busy && !dirty && config_valid_o && run_enable_o;
    wire bad_command = command && (sel_i!=15 || (wdata_i!=1 && wdata_i!=2 && wdata_i!=4));
    wire [31:0] mask = {{8{sel_i[3]}},{8{sel_i[2]}},{8{sel_i[1]}},{8{sel_i[0]}}};
    wire aligned_mapped = addr_i[1:0]==0 && addr_i<=16'h44;
    wire ro = addr_i<=8 || addr_i==16'h14 || addr_i==16'h18 || addr_i==16'h1c;
    wire bad_access = !aligned_mapped || (we_i && ro) ||
        (we_i && addr_i==16'h24 && (wdata_i & mask & 32'hfffffffe)!=0);
    reg past_valid=0;
    reg [5:0] seen_halves=0;
    reg [11:0] cover_seen=0;
    assign reached=cover_seen;
    always @(posedge clk) begin
        past_valid <= 1;
        if (!past_valid) assume(rst);
        if (past_valid) begin
            // p_decode
            assert(error_o==bad_access);
            if ($past(rst)) begin
                // p_reset_active
                assert(active==0);
                // p_reset_flags
                assert(!config_valid_o && !dirty && !run_enable_o && !start_o);
                // p_reset_sticky
                assert(errors==0 && !done_sticky && sequence_number==0);
                // p_reset_shadow
                assert(shadow==288'(ENGINE_KIND));
            end else begin
                // p_atomic_all_pairs
                assert(active==($past(accepted) ? $past(candidate) : $past(active)));
                // p_sequence
                assert(sequence_number==$past(sequence_number)+($past(accepted) ? 32'd1 : 32'd0));
                // p_valid
                assert(config_valid_o==($past(config_valid_o) || $past(accepted)));
                // p_dirty
                assert(dirty==($past(shadow_write) || (!$past(accepted) && $past(dirty))));
                // p_start
                assert(start_o==$past(start_ok));
                // p_done
                assert(done_sticky==(($past(engine_done_i) && ENGINE_KIND!=0) ||
                    (!$past(clear) && $past(done_sticky))));
                // p_clear_errors
                if ($past(clear)) assert(errors==0);
                // p_sticky
                if (!$past(clear)) assert((errors & $past(errors))==$past(errors));
                // p_busy_commit
                if ($past(commit && busy)) assert(errors[0] && active==$past(active));
                // p_busy_start
                if ($past(launch && busy)) assert(errors[1] && !start_o);
                // p_dirty_start
                if ($past(launch && dirty)) assert(errors[2] && !start_o);
                // p_invalid_start
                if ($past(launch && !config_valid_o)) assert(errors[3] && !start_o);
                // p_invalid_commit
                if ($past(commit && !good_config)) assert(errors[4] && active==$past(active));
                // p_bad_command
                if ($past(bad_command)) assert(errors[5] && active==$past(active) && !start_o);
                // p_illegal_bus
                if ($past(req_i && bad_access)) assert(errors[6]);
                // p_disabled_start
                if ($past(launch && !run_enable_o)) assert(errors[7] && !start_o);
                // p_run
                assert(run_enable_o==($past(req_i && we_i && addr_i==16'h24 && !bad_access && sel_i[0]) ?
                    $past(wdata_i[0]) : $past(run_enable_o)));
            end
        end
        if (rst) begin seen_halves<=0; cover_seen<=0; end
        else begin
            if (shadow_write && addr_i>=16'h28 && addr_i<=16'h3c)
                seen_halves[(addr_i-16'h28)>>2]<=1;
            if (accepted) begin cover_seen[0]<=1; if (sequence_number==1) cover_seen[1]<=1; end
            if (start_ok) cover_seen[2]<=1;
            if (launch && dirty) cover_seen[3]<=1;
            if (commit && busy) cover_seen[4]<=1;
            if (clear && errors!=0) cover_seen[5]<=1;
            for (integer k=0;k<3;k=k+1) begin
                if (shadow_write && addr_i==16'h2c+16'(8*k) && seen_halves[2*k]) cover_seen[6+2*k]<=1;
                if (shadow_write && addr_i==16'h28+16'(8*k) && seen_halves[2*k+1]) cover_seen[7+2*k]<=1;
            end
        end
    end
    for (genvar k=0;k<9;k=k+1) begin: shadow_properties
        localparam [15:0] ADDRESS = k==0 ? 16'h20 : 16'h24+16'(4*k);
        always @(posedge clk) if (past_valid && !$past(rst)) begin
            // p_shadow_byte_write
            assert(shadow[32*k+:32] ==
                ($past(shadow_write && addr_i==ADDRESS) ?
                 (($past(shadow[32*k+:32]) & ~$past(mask)) | ($past(wdata_i) & $past(mask))) :
                 $past(shadow[32*k+:32])));
        end
    end
endmodule
