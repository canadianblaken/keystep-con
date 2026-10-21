// Post-analysis: dump functions, strings with referencing functions, and decompiled C.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import java.io.*;
import java.util.*;

public class KspExport extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = getScriptArgs().length > 0 ? getScriptArgs()[0] : "/tmp";
        String tag = currentProgram.getName().replace(".elf", "");
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();

        try (PrintWriter w = new PrintWriter(out + "/" + tag + "_functions.tsv")) {
            w.println("addr\tname\tsize\tcallers\tcallees");
            for (Function f : fm.getFunctions(true))
                w.printf("%s\t%s\t%d\t%d\t%d%n", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses(),
                    f.getCallingFunctions(monitor).size(), f.getCalledFunctions(monitor).size());
        }
        try (PrintWriter w = new PrintWriter(out + "/" + tag + "_strings.tsv")) {
            w.println("addr\tfuncs\tstring");
            for (Data d : currentProgram.getListing().getDefinedData(true)) {
                if (!d.hasStringValue()) continue;
                Set<String> fs = new TreeSet<>();
                for (Reference r : rm.getReferencesTo(d.getAddress())) {
                    Function f = fm.getFunctionContaining(r.getFromAddress());
                    fs.add(f == null ? "?" + r.getFromAddress() : f.getEntryPoint().toString());
                }
                String s = String.valueOf(d.getValue()).replace("\t", "\\t").replace("\n", "\\n");
                w.printf("%s\t%s\t%s%n", d.getAddress(), String.join(",", fs), s);
            }
        }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(out + "/" + tag + "_decomp.c")) {
            for (Function f : fm.getFunctions(true)) {
                if (monitor.isCancelled()) break;
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                w.println("// ==== " + f.getEntryPoint() + " " + f.getName());
                w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
            }
        }
        println("export done: " + fm.getFunctionCount() + " functions");
    }
}
