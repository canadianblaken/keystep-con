// Pre-analysis: seed functions from the Cortex-M vector table at the image base.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;

public class KspVectors extends GhidraScript {
    @Override
    public void run() throws Exception {
        MemoryBlock[] blocks = currentProgram.getMemory().getBlocks();
        Address base = null;
        for (MemoryBlock b : blocks) if (b.isExecute() && b.isInitialized()) { base = b.getStart(); break; }
        Memory mem = currentProgram.getMemory();
        int n = 0;
        for (int i = 1; i < 128; i++) {
            Address slot = base.add(i * 4);
            long v = mem.getInt(slot) & 0xffffffffL;
            if ((v & 1) == 0 || v < base.getOffset() || v > base.getOffset() + 0x100000) continue;
            Address tgt = toAddr(v & ~1L);
            createDWord(slot);
            if (getInstructionAt(tgt) == null) {
                try {
                    currentProgram.getProgramContext().setValue(
                        currentProgram.getProgramContext().getRegister("TMode"), tgt, tgt, java.math.BigInteger.ONE);
                } catch (Exception e) { println("ctx skip " + tgt + ": " + e.getMessage()); }
                disassemble(tgt);
            }
            if (getFunctionAt(tgt) != null) { n++; continue; }
            createFunction(tgt, i == 1 ? "Reset_Handler" : String.format("vec_%02d", i));
            n++;
        }
        println("seeded " + n + " vectors from " + base);
    }
}
