// Create functions at the given hex addresses (if missing) and print their decompilation.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;

public class KspDecompAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (String a : getScriptArgs()) {
            Address ad = toAddr(Long.parseLong(a, 16));
            Function f = getFunctionAt(ad);
            if (f != null && getInstructionAt(ad) != null && !getInstructionAt(ad).getPrototype().getLanguage().getProcessor().toString().isEmpty()) {}
            if (f != null) removeFunction(f);
            clearListing(ad, ad.add(0x100));
            currentProgram.getProgramContext().setValue(currentProgram.getProgramContext().getRegister("TMode"), ad, ad.add(0x100), java.math.BigInteger.ONE);
            disassemble(ad);
            f = getFunctionAt(ad);
            if (f == null) f = createFunction(ad, "FUN_" + a);
            DecompileResults r = di.decompileFunction(f, 60, monitor);
            println("==== " + a + "\n" + (r.decompileCompleted() ? r.getDecompiledFunction().getC() : r.getErrorMessage()));
        }
    }
}
