// The KOTOR reverse-engineering pipeline's one Ghidra script. It writes the plain-text exports
// under kotor/re/export/ that agents grep, re-decompiles functions on demand, and applies the
// shared names database (kotor/docs/re/names.tsv). Drive it through kotor/tools/py/re.py rather
// than by hand; that wrapper finds Ghidra, serialises access to the project and passes the args.
//
// Script arguments (first one is the mode):
//   export-all EXPORT_DIR                  every export, every function decompiled
//   export-tables EXPORT_DIR               every export except the decompiled functions
//   fixup EXPORT_DIR                       once after import: functions at code pointers in
//                                          data, strings at referenced addresses; re-analyzes
//   decompile EXPORT_DIR ADDR... | @FILE   re-decompile these functions (any address inside one)
//   apply-names EXPORT_DIR NAMES_TSV STATE_TSV [all]
//                                          apply rows of NAMES_TSV that changed since STATE_TSV,
//                                          then re-export the functions that show the new names
//
// This file holds no code or data from the game; it only reads the analyzed program.
// @category KOTOR

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;

import ghidra.app.cmd.function.ApplyFunctionSignatureCmd;
import ghidra.app.cmd.function.FunctionRenameOption;
import ghidra.app.decompiler.*;
import ghidra.app.decompiler.parallel.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.services.DataTypeManagerService;
import ghidra.app.util.NamespaceUtils;
import ghidra.app.util.cparser.C.CParserUtils;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.util.DefinedStringIterator;
import ghidra.util.data.DataTypeParser;
import ghidra.util.task.TaskMonitor;

public class KotorRE extends GhidraScript {

    static final int HEADER_CAP = 60;      // list entries per header section before "+N more"
    static final int DECOMPILE_TIMEOUT = 180;

    Path exportDir;
    Path fnDir;
    Listing listing;
    FunctionManager fm;
    ReferenceManager rm;
    SymbolTable st;
    Memory mem;
    AddressSet textSet = new AddressSet();
    AddressSet dataSet = new AddressSet();   // .rdata, .data (incl. bss), .rsrc

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            throw new IllegalArgumentException("usage: MODE EXPORT_DIR ...");
        }
        String mode = args[0];
        exportDir = Paths.get(args[1]);
        fnDir = exportDir.resolve("functions");
        Files.createDirectories(fnDir);
        listing = currentProgram.getListing();
        fm = currentProgram.getFunctionManager();
        rm = currentProgram.getReferenceManager();
        st = currentProgram.getSymbolTable();
        mem = currentProgram.getMemory();
        for (MemoryBlock b : mem.getBlocks()) {
            if (b.isExecute()) {
                textSet.add(b.getStart(), b.getEnd());
            }
            else if (!b.isExternalBlock() && !b.getName().startsWith("Headers")) {
                dataSet.add(b.getStart(), b.getEnd());
            }
        }

        long t0 = System.currentTimeMillis();
        switch (mode) {
            case "export-all":
                exportTables();
                decompileAll();
                break;
            case "export-tables":
                exportTables();
                break;
            case "fixup":
                fixup();
                break;
            case "asm":
                writeAsm(resolveFunctions(Arrays.copyOfRange(args, 2, args.length)));
                break;
            case "decompile":
                decompileSome(resolveFunctions(Arrays.copyOfRange(args, 2, args.length)));
                break;
            case "apply-names":
                applyNames(Paths.get(args[2]), Paths.get(args[3]),
                    args.length > 4 && args[4].equals("all"));
                break;
            default:
                throw new IllegalArgumentException("unknown mode " + mode);
        }
        println(String.format("KOTOR: %s done in %.1f s", mode,
            (System.currentTimeMillis() - t0) / 1000.0));
    }

    // ---------------------------------------------------------------- formatting helpers

    static String hex(Address a) {
        return String.format("0x%08x", a.getOffset());
    }

    static String hex(long v) {
        return String.format("0x%08x", v);
    }

    static String esc(String s) {
        StringBuilder b = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '\t': b.append("\\t"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                default:
                    if (c < 0x20 || c == 0x7f) {
                        b.append(String.format("\\x%02x", (int) c));
                    }
                    else {
                        b.append(c);
                    }
            }
        }
        return b.toString();
    }

    // Windows refuses to delete or replace a file another process has open (an agent reading
    // the exports at that moment): retry for a while instead of failing the whole run.
    static void moveRetrying(Path from, Path to) throws IOException {
        for (int i = 0;; i++) {
            try {
                Files.move(from, to, StandardCopyOption.REPLACE_EXISTING);
                return;
            }
            catch (FileSystemException e) {
                if (i >= 100) {
                    throw e;
                }
                sleepQuietly(100);
            }
        }
    }

    static void deleteRetrying(Path p) throws IOException {
        for (int i = 0;; i++) {
            try {
                Files.deleteIfExists(p);
                return;
            }
            catch (FileSystemException e) {
                if (i >= 100) {
                    throw e;
                }
                sleepQuietly(100);
            }
        }
    }

    static void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        }
        catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    static String fileName(Function f) {
        String n = f.getName(true).replace("::", "__").replaceAll("[^A-Za-z0-9_.-]", "_");
        if (n.length() > 100) {
            n = n.substring(0, 100);
        }
        return String.format("%08x_%s.c", f.getEntryPoint().getOffset(), n);
    }

    static String className(Function f) {
        Namespace ns = f.getParentNamespace();
        if (ns == null || ns.isGlobal() || ns instanceof Library) {
            return "";
        }
        return ns.getName(true);
    }

    String fnLabel(Function f) {
        return hex(f.getEntryPoint()) + " " + f.getName(true);
    }

    Address toAddr32(long v) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
    }

    // The string at a, if a defined string starts there.
    String stringAt(Address a) {
        Data d = listing.getDataAt(a);
        if (d == null || !StringDataInstance.isString(d)) {
            return null;
        }
        String s = StringDataInstance.getStringDataInstance(d).getStringValue();
        return s;
    }

    // "DLL!name" if a is an import (an external location, or an IAT slot pointing at one).
    String importAt(Address a) {
        if (a.isExternalAddress()) {
            Symbol s = st.getPrimarySymbol(a);
            if (s != null && s.isExternal()) {
                ExternalLocation loc = currentProgram.getExternalManager().getExternalLocation(s);
                if (loc != null) {
                    return loc.getLibraryName() + "!" + loc.getLabel();
                }
                return s.getName(true);
            }
            return null;
        }
        for (Reference r : rm.getReferencesFrom(a)) {
            if (r.isExternalReference()) {
                ExternalLocation loc = ((ExternalReference) r).getExternalLocation();
                return loc.getLibraryName() + "!" + loc.getLabel();
            }
        }
        return null;
    }

    // ---------------------------------------------------------------- per-function facts

    static class Info {
        Function f;
        // callers: functions with a call/jump to the entry; ptrRefs: other references to it
        TreeMap<Long, String> callers = new TreeMap<>();
        TreeMap<Long, String> ptrRefs = new TreeMap<>();
        TreeMap<Long, String> callees = new TreeMap<>();
        TreeSet<String> imports = new TreeSet<>();
        TreeMap<Long, String> strings = new TreeMap<>();
        TreeMap<Long, String> globals = new TreeMap<>();
        TreeMap<Long, String> fnPtrs = new TreeMap<>();   // functions whose address it takes
    }

    Info info(Function f) {
        Info in = new Info();
        in.f = f;
        Address entry = f.getEntryPoint();
        for (Reference r : rm.getReferencesTo(entry)) {
            Address from = r.getFromAddress();
            Function g = fm.getFunctionContaining(from);
            RefType t = r.getReferenceType();
            if (g != null && (t.isCall() || t.isJump())) {
                if (!g.equals(f) || t.isCall()) {
                    in.callers.put(g.getEntryPoint().getOffset(), g.getName(true));
                }
            }
            else if (g != null) {
                in.ptrRefs.put(from.getOffset(), "in " + g.getName(true));
            }
            else if (!from.isExternalAddress() && from.isMemoryAddress()) {
                Symbol s = st.getPrimarySymbol(from);
                in.ptrRefs.put(from.getOffset(), "data" + (s != null ? " " + s.getName(true) : ""));
            }
        }
        AddressIterator it = rm.getReferenceSourceIterator(f.getBody(), true);
        while (it.hasNext()) {
            Address from = it.next();
            for (Reference r : rm.getReferencesFrom(from)) {
                Address to = r.getToAddress();
                RefType t = r.getReferenceType();
                if (r.isExternalReference()) {
                    String imp = importAt(to);
                    if (imp != null) {
                        in.imports.add(imp);
                    }
                    continue;
                }
                if (!to.isMemoryAddress()) {
                    continue;
                }
                Function g = fm.getFunctionAt(to);
                if (g != null) {
                    if (t.isCall() || (t.isJump() && !g.equals(f))) {
                        if (g.isThunk() && g.getThunkedFunction(true) != null
                            && g.getThunkedFunction(true).isExternal()) {
                            String imp = importAt(g.getThunkedFunction(true).getEntryPoint());
                            if (imp != null) {
                                in.imports.add(imp);
                            }
                        }
                        in.callees.put(to.getOffset(), g.getName(true));
                    }
                    else if (!t.isFlow()) {
                        in.fnPtrs.put(to.getOffset(), g.getName(true));
                    }
                    continue;
                }
                if (f.getBody().contains(to)) {
                    continue;
                }
                String imp = importAt(to);
                if (imp != null) {
                    in.imports.add(imp);
                    continue;
                }
                String s = stringAt(to);
                if (s != null) {
                    in.strings.put(to.getOffset(), s);
                    continue;
                }
                if (dataSet.contains(to)) {
                    Symbol sym = st.getPrimarySymbol(to);
                    in.globals.put(to.getOffset(), sym != null ? sym.getName(true) : "");
                }
            }
        }
        return in;
    }

    static void section(StringBuilder b, String title, Map<Long, String> m, boolean quote) {
        if (m.isEmpty()) {
            return;
        }
        b.append("// ").append(title).append(" (").append(m.size()).append("):\n");
        int n = 0;
        for (Map.Entry<Long, String> e : m.entrySet()) {
            if (n++ == HEADER_CAP) {
                b.append("//   ... +").append(m.size() - HEADER_CAP)
                    .append(" more (re.py callers/xrefs lists all)\n");
                break;
            }
            String v = e.getValue();
            if (quote) {
                v = "\"" + esc(v.length() > 160 ? v.substring(0, 160) + "..." : v) + "\"";
            }
            b.append(String.format("//   0x%08x %s\n", e.getKey(), v));
        }
    }

    String header(Info in) {
        Function f = in.f;
        StringBuilder b = new StringBuilder();
        b.append("// ").append(hex(f.getEntryPoint())).append("  ").append(f.getName(true))
            .append("  size=").append(f.getBody().getNumAddresses()).append('\n');
        b.append("// signature: ").append(f.getSignature().getPrototypeString(true)).append('\n');
        if (f.isThunk() && f.getThunkedFunction(false) != null) {
            b.append("// thunk to: ").append(f.getThunkedFunction(false).getName(true)).append('\n');
        }
        String plate = f.getComment();
        if (plate != null && !plate.isEmpty()) {
            for (String line : plate.split("\n")) {
                b.append("// note: ").append(line).append('\n');
            }
        }
        section(b, "callers", in.callers, false);
        section(b, "address taken at", in.ptrRefs, false);
        section(b, "callees", in.callees, false);
        if (!in.imports.isEmpty()) {
            b.append("// imports: ").append(String.join(", ", in.imports)).append('\n');
        }
        section(b, "strings", in.strings, true);
        section(b, "globals", in.globals, false);
        section(b, "function pointers taken", in.fnPtrs, false);
        b.append("\n");
        return b.toString();
    }

    String indexRow(Info in, String status) {
        Function f = in.f;
        String sig = f.getSignature().getPrototypeString(true).replace('\t', ' ').replace('\n', ' ');
        return String.join("\t", hex(f.getEntryPoint()), f.getName(true),
            Long.toString(f.getBody().getNumAddresses()), Integer.toString(in.callers.size()),
            Integer.toString(in.callees.size()), className(f),
            f.getSymbol().getSource().toString(), status, sig);
    }

    static final String INDEX_HEADER =
        "addr\tname\tsize\tn_callers\tn_callees\tclass\tsource\tdecomp\tsignature";

    // ---------------------------------------------------------------- decompilation

    class Result {
        long addr;
        String row;
    }

    DecompilerCallback<Result> callback() {
        DecompilerCallback<Result> cb = new DecompilerCallback<Result>(currentProgram,
            new DecompileConfigurer() {
                @Override
                public void configure(DecompInterface d) {
                    DecompileOptions o = new DecompileOptions();
                    o.grabFromProgram(currentProgram);
                    d.setOptions(o);
                    d.toggleCCode(true);
                    d.toggleSyntaxTree(false);
                    d.setSimplificationStyle("decompile");
                }
            }) {
            @Override
            public Result process(DecompileResults res, TaskMonitor m) throws Exception {
                Function f = res.getFunction();
                Info in = info(f);
                String status;
                String body;
                if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
                    status = "ok";
                    body = res.getDecompiledFunction().getC();
                }
                else {
                    String err = res.getErrorMessage();
                    status = res.isTimedOut() ? "timeout" : "failed";
                    body = "// decompile " + status + ": "
                        + (err == null ? "" : err.trim().replace("\n", "\n// ")) + "\n";
                }
                writeFunctionFile(f, header(in) + body);
                Result r = new Result();
                r.addr = f.getEntryPoint().getOffset();
                r.row = indexRow(in, status);
                return r;
            }
        };
        cb.setTimeout(DECOMPILE_TIMEOUT);
        return cb;
    }

    void writeFunctionFile(Function f, String text) throws IOException {
        String name = fileName(f);
        String prefix = name.substring(0, 9);   // "xxxxxxxx_"
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(fnDir, prefix + "*.c")) {
            for (Path p : ds) {
                if (!p.getFileName().toString().equals(name)) {
                    deleteRetrying(p);
                }
            }
        }
        Files.write(fnDir.resolve(name), text.getBytes(StandardCharsets.UTF_8));
    }

    List<Function> allFunctions() {
        List<Function> out = new ArrayList<>();
        for (Function f : fm.getFunctions(true)) {
            out.add(f);
        }
        return out;
    }

    void decompileAll() throws Exception {
        List<Function> fns = allFunctions();
        println("KOTOR: decompiling " + fns.size() + " functions");
        // Old files of functions that no longer exist would mislead a grep: start clean.
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(fnDir, "*.c")) {
            for (Path p : ds) {
                deleteRetrying(p);
            }
        }
        long t0 = System.currentTimeMillis();
        DecompilerCallback<Result> cb = callback();
        List<Result> results;
        try {
            results = ParallelDecompiler.decompileFunctions(cb, fns, monitor);
        }
        finally {
            cb.dispose();
        }
        TreeMap<Long, String> rows = new TreeMap<>();
        for (Result r : results) {
            if (r != null) {
                rows.put(r.addr, r.row);
            }
        }
        writeIndex(rows);
        println(String.format("KOTOR: decompiled %d functions in %.1f s", rows.size(),
            (System.currentTimeMillis() - t0) / 1000.0));
    }

    void decompileSome(Collection<Function> fns) throws Exception {
        if (fns.isEmpty()) {
            println("KOTOR: nothing to decompile");
            return;
        }
        TreeMap<Long, String> rows = readIndex();
        DecompilerCallback<Result> cb = callback();
        List<Result> results;
        try {
            results = ParallelDecompiler.decompileFunctions(cb, new ArrayList<>(fns), monitor);
        }
        finally {
            cb.dispose();
        }
        int done = 0;
        for (Result r : results) {
            if (r != null) {
                rows.put(r.addr, r.row);
                done++;
                if (results.size() <= 20) {
                    println("KOTOR: decompiled " + r.row.split("\t")[0] + " "
                        + r.row.split("\t")[1] + " -> functions/" + fileName(fm.getFunctionAt(
                            toAddr32(r.addr))));
                }
            }
        }
        if (results.size() > 20) {
            println("KOTOR: decompiled " + done + " functions");
        }
        // Drop rows of functions that no longer exist (removed by hand in Ghidra).
        rows.keySet().removeIf(a -> fm.getFunctionAt(toAddr32(a)) == null);
        writeIndex(rows);
    }

    TreeMap<Long, String> readIndex() throws IOException {
        TreeMap<Long, String> rows = new TreeMap<>();
        Path p = exportDir.resolve("functions.tsv");
        if (!Files.exists(p)) {
            return rows;
        }
        for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
            if (line.startsWith("addr\t") || line.isEmpty()) {
                continue;
            }
            rows.put(Long.parseLong(line.substring(2, 10), 16), line);
        }
        return rows;
    }

    void writeIndex(TreeMap<Long, String> rows) throws IOException {
        Path tmp = exportDir.resolve("functions.tsv.tmp");
        try (BufferedWriter w = Files.newBufferedWriter(tmp, StandardCharsets.UTF_8)) {
            w.write(INDEX_HEADER);
            w.write('\n');
            for (String r : rows.values()) {
                w.write(r);
                w.write('\n');
            }
        }
        moveRetrying(tmp, exportDir.resolve("functions.tsv"));
    }

    List<Function> resolveFunctions(String[] specs) throws IOException {
        List<String> items = new ArrayList<>();
        for (String s : specs) {
            if (s.startsWith("@")) {
                for (String line : Files.readAllLines(Paths.get(s.substring(1)))) {
                    line = line.trim();
                    if (!line.isEmpty() && !line.startsWith("#")) {
                        items.add(line.split("\\s+")[0]);
                    }
                }
            }
            else {
                items.add(s);
            }
        }
        LinkedHashSet<Function> out = new LinkedHashSet<>();
        for (String s : items) {
            Address a = toAddr32(Long.parseLong(s.replaceFirst("^0[xX]", ""), 16));
            Function f = fm.getFunctionContaining(a);
            if (f == null) {
                println("KOTOR: no function at " + s);
                continue;
            }
            out.add(f);
        }
        return new ArrayList<>(out);
    }

    // ---------------------------------------------------------------- disassembly

    // A listing per function, each instruction annotated with what it refers to.
    void writeAsm(List<Function> fns) throws IOException {
        Path dir = exportDir.resolve("asm");
        Files.createDirectories(dir);
        for (Function f : fns) {
            StringBuilder b = new StringBuilder();
            b.append("; ").append(hex(f.getEntryPoint())).append("  ").append(f.getName(true))
                .append("  ").append(f.getSignature().getPrototypeString(true)).append('\n');
            for (Instruction ins : listing.getInstructions(f.getBody(), true)) {
                Address a = ins.getAddress();
                if (!a.equals(f.getEntryPoint())) {
                    Symbol s = st.getPrimarySymbol(a);
                    if (s != null) {
                        b.append(s.getName()).append(":\n");
                    }
                }
                StringBuilder bytes = new StringBuilder();
                try {
                    for (byte x : ins.getBytes()) {
                        bytes.append(String.format("%02x", x & 0xff));
                    }
                }
                catch (MemoryAccessException e) {
                    bytes.append("??");
                }
                StringBuilder note = new StringBuilder();
                for (Reference r : ins.getReferencesFrom()) {
                    Address to = r.getToAddress();
                    String what = null;
                    Function g = to.isMemoryAddress() ? fm.getFunctionAt(to) : null;
                    if (g != null) {
                        what = g.getName(true);
                    }
                    else if (r.isExternalReference() || importAt(to) != null) {
                        what = importAt(to);
                    }
                    else if (to.isMemoryAddress() && stringAt(to) != null) {
                        String s = stringAt(to);
                        what = "\"" + esc(s.length() > 60 ? s.substring(0, 60) + "..." : s)
                            + "\"";
                    }
                    else if (to.isMemoryAddress() && !f.getBody().contains(to)) {
                        Symbol s = st.getPrimarySymbol(to);
                        what = s != null ? s.getName(true) : null;
                    }
                    if (what != null) {
                        note.append(note.length() == 0 ? "  ; " : ", ").append(what);
                    }
                }
                b.append(String.format("  %08x  %-20s %s%s\n", a.getOffset(), bytes,
                    ins.toString(), note));
            }
            String name = fileName(f).replaceAll("\\.c$", ".s");
            String prefix = name.substring(0, 9);
            try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, prefix + "*.s")) {
                for (Path p : ds) {
                    deleteRetrying(p);
                }
            }
            Files.write(dir.resolve(name), b.toString().getBytes(StandardCharsets.UTF_8));
        }
        println("KOTOR: wrote " + fns.size() + " listings to " + dir);
    }

    // ---------------------------------------------------------------- fixups after import

    // Ghidra makes functions only where code calls; virtual functions and table-driven handlers
    // are reached through pointers in data, so make them functions too. Short strings (GFF
    // labels, 2DA columns) are below the string analyzer's minimum length: define the ones that
    // code or pointer data reference.
    void fixup() throws Exception {
        for (int pass = 1; pass <= 3; pass++) {
            int fns = fixupCodePointers();
            int strs = fixupStrings();
            println("KOTOR: fixup pass " + pass + ": " + fns + " functions, " + strs
                + " strings created");
            analyzeChanges(currentProgram);
            if (fns == 0 && strs == 0) {
                break;
            }
        }
        println("KOTOR: functions now " + fm.getFunctionCount());
    }

    static long dword(byte[] b, int i) {
        return (b[i] & 0xffL) | (b[i + 1] & 0xffL) << 8 | (b[i + 2] & 0xffL) << 16
            | (b[i + 3] & 0xffL) << 24;
    }

    List<MemoryBlock> dataBlocks() {
        List<MemoryBlock> out = new ArrayList<>();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isExecute() && b.isInitialized() && !b.isExternalBlock()
                && !b.getName().startsWith("Headers") && !b.getName().equals(".rsrc")) {
                out.add(b);
            }
        }
        return out;
    }

    boolean isCodePtr(long v) {
        return v >= 0x400000L && v <= 0xffffffffL && textSet.contains(toAddr32(v));
    }

    int fixupCodePointers() throws Exception {
        int created = 0;
        for (MemoryBlock b : dataBlocks()) {
            int len = (int) b.getSize();
            byte[] bytes = new byte[len];
            b.getBytes(b.getStart(), bytes);
            int n = len / 4;
            for (int i = 0; i < n; i++) {
                long v = dword(bytes, i * 4);
                if (!isCodePtr(v)) {
                    continue;
                }
                // Only runs of two or more code pointers with nothing between: vtables and
                // handler tables. Records mixing code pointers with integers are mostly the
                // compiler's exception-unwind maps, whose targets are funclets.
                boolean prev = i > 0 && isCodePtr(dword(bytes, (i - 1) * 4));
                boolean next = i + 1 < n && isCodePtr(dword(bytes, (i + 1) * 4));
                if (!prev && !next) {
                    continue;
                }
                Address site = b.getStart().add(4L * i);
                Data d = listing.getDefinedDataContaining(site);
                if (d != null && !(d.getDataType() instanceof Pointer)
                    && !(d.getDataType() instanceof Array)) {
                    continue;
                }
                Address t = toAddr32(v);
                if (fm.getFunctionAt(t) != null) {
                    continue;
                }
                if (listing.getInstructionAt(t) == null) {
                    if (listing.getInstructionContaining(t) != null
                        || listing.getDefinedDataContaining(t) != null) {
                        continue;
                    }
                    disassemble(t);
                    if (listing.getInstructionAt(t) == null) {
                        continue;
                    }
                }
                if (d == null) {
                    try {
                        createData(site, PointerDataType.dataType);
                    }
                    catch (Exception e) {
                        // overlapping data: leave it
                    }
                }
                Function f = createFunction(t, null);
                if (f != null) {
                    created++;
                }
            }
        }
        // Code whose address is taken (callbacks, handlers stored by an init routine, single
        // function pointers in data) but that no function contains yet.
        AddressIterator it = rm.getReferenceDestinationIterator(textSet, true);
        List<Address> targets = new ArrayList<>();
        while (it.hasNext()) {
            targets.add(it.next());
        }
        for (Address t : targets) {
            if (fm.getFunctionContaining(t) != null) {
                continue;
            }
            boolean taken = false;
            for (Reference r : rm.getReferencesTo(t)) {
                if (!r.getReferenceType().isFlow()) {
                    taken = true;
                    break;
                }
            }
            if (!taken) {
                continue;
            }
            if (listing.getInstructionAt(t) == null) {
                if (listing.getInstructionContaining(t) != null
                    || listing.getDefinedDataContaining(t) != null) {
                    continue;
                }
                disassemble(t);
                if (listing.getInstructionAt(t) == null) {
                    continue;
                }
            }
            if (createFunction(t, null) != null) {
                created++;
            }
        }
        // Single code pointers in data that point at code no function contains.
        for (MemoryBlock b : dataBlocks()) {
            int len = (int) b.getSize();
            byte[] bytes = new byte[len];
            b.getBytes(b.getStart(), bytes);
            for (int i = 0; i + 4 <= len; i += 4) {
                long v = dword(bytes, i);
                if (!isCodePtr(v)) {
                    continue;
                }
                Address t = toAddr32(v);
                if (listing.getInstructionAt(t) == null || fm.getFunctionContaining(t) != null) {
                    continue;
                }
                if (createFunction(t, null) != null) {
                    created++;
                }
            }
        }
        return created;
    }

    // Length of the printable NUL-terminated ASCII string at a, or -1.
    int asciiLength(Address a) {
        try {
            byte[] buf = new byte[512];
            int got = mem.getBytes(a, buf);
            for (int i = 0; i < got; i++) {
                int c = buf[i] & 0xff;
                if (c == 0) {
                    return i;
                }
                if (!(c >= 0x20 && c < 0x7f) && c != 9 && c != 10 && c != 13) {
                    return -1;
                }
            }
        }
        catch (Exception e) {
            // unreadable
        }
        return -1;
    }

    boolean tryString(Address t, int min) {
        if (!dataSet.contains(t) || listing.getDefinedDataContaining(t) != null) {
            return false;
        }
        MemoryBlock mb = mem.getBlock(t);
        if (mb == null || !mb.isInitialized()) {
            return false;
        }
        int len = asciiLength(t);
        if (len < min) {
            return false;
        }
        try {
            if (listing.getDefinedDataContaining(t.add(len)) != null) {
                return false;
            }
            createAsciiString(t);
            return true;
        }
        catch (Exception e) {
            return false;
        }
    }

    int fixupStrings() throws Exception {
        int created = 0;
        // Strings that instructions point at.
        AddressIterator it = rm.getReferenceDestinationIterator(dataSet, true);
        List<Address> dests = new ArrayList<>();
        while (it.hasNext()) {
            dests.add(it.next());
        }
        for (Address t : dests) {
            boolean fromCode = false;
            for (Reference r : rm.getReferencesTo(t)) {
                if (listing.getInstructionAt(r.getFromAddress()) != null) {
                    fromCode = true;
                    break;
                }
            }
            if (fromCode && tryString(t, 2)) {
                created++;
            }
        }
        // Strings that pointer tables in data point at (name tables, field label lists).
        for (MemoryBlock b : dataBlocks()) {
            int len = (int) b.getSize();
            byte[] bytes = new byte[len];
            b.getBytes(b.getStart(), bytes);
            for (int i = 0; i + 4 <= len; i += 4) {
                long v = dword(bytes, i);
                if (v < 0x400000L || v > 0xffffffffL) {
                    continue;
                }
                Address t = toAddr32(v);
                if (!dataSet.contains(t)) {
                    continue;
                }
                Address site = b.getStart().add(i);
                if (listing.getDefinedDataContaining(site) != null) {
                    continue;
                }
                boolean made = tryString(t, 3);
                if (made || stringAt(t) != null) {
                    try {
                        createData(site, PointerDataType.dataType);
                    }
                    catch (Exception e) {
                        // leave it
                    }
                }
                if (made) {
                    created++;
                }
            }
        }
        return created;
    }

    // ---------------------------------------------------------------- whole-program tables

    void exportTables() throws Exception {
        long t0 = System.currentTimeMillis();
        exportCalls();
        exportStrings();
        exportImports();
        exportPointerTables();
        exportGlobals();
        exportRtti();
        exportSegments();
        println(String.format("KOTOR: tables exported in %.1f s",
            (System.currentTimeMillis() - t0) / 1000.0));
    }

    // Writes NAME.tmp and moves it over NAME on close, so readers never see half a table.
    BufferedWriter writer(String name) throws IOException {
        Path dest = exportDir.resolve(name);
        Path tmp = exportDir.resolve(name + ".tmp");
        return new BufferedWriter(new OutputStreamWriter(Files.newOutputStream(tmp),
            StandardCharsets.UTF_8)) {
            @Override
            public void close() throws IOException {
                super.close();
                moveRetrying(tmp, dest);
            }
        };
    }

    void exportCalls() throws IOException {
        int n = 0;
        try (BufferedWriter w = writer("calls.tsv")) {
            w.write("caller\tcallee\tkind\tsite\n");
            for (Function f : fm.getFunctions(true)) {
                AddressIterator it = rm.getReferenceSourceIterator(f.getBody(), true);
                while (it.hasNext()) {
                    Address from = it.next();
                    for (Reference r : rm.getReferencesFrom(from)) {
                        Address to = r.getToAddress();
                        if (!to.isMemoryAddress()) {
                            continue;
                        }
                        Function g = fm.getFunctionAt(to);
                        if (g == null) {
                            continue;
                        }
                        RefType t = r.getReferenceType();
                        String kind = t.isCall() ? "call" : t.isJump() ? "jump" : "ref";
                        if (kind.equals("jump") && g.equals(f)) {
                            continue;
                        }
                        w.write(hex(f.getEntryPoint()) + "\t" + hex(to) + "\t" + kind + "\t"
                            + hex(from) + "\n");
                        n++;
                    }
                }
            }
        }
        println("KOTOR: calls.tsv " + n + " edges");
    }

    void exportStrings() throws IOException {
        int n = 0;
        try (BufferedWriter w = writer("strings.tsv")) {
            w.write("addr\tlen\ttype\tref_functions\tref_data\ttext\n");
            for (Data d : DefinedStringIterator.forProgram(currentProgram)) {
                StringDataInstance sdi = StringDataInstance.getStringDataInstance(d);
                String s = sdi.getStringValue();
                if (s == null) {
                    continue;
                }
                Address a = d.getAddress();
                TreeSet<Long> fns = new TreeSet<>();
                TreeSet<Long> datas = new TreeSet<>();
                for (Reference r : rm.getReferencesTo(a)) {
                    Function g = fm.getFunctionContaining(r.getFromAddress());
                    if (g != null) {
                        fns.add(g.getEntryPoint().getOffset());
                    }
                    else if (r.getFromAddress().isMemoryAddress()) {
                        datas.add(r.getFromAddress().getOffset());
                    }
                }
                w.write(hex(a) + "\t" + d.getLength() + "\t" + d.getDataType().getName() + "\t"
                    + join(fns) + "\t" + join(datas) + "\t" + esc(s) + "\n");
                n++;
            }
        }
        println("KOTOR: strings.tsv " + n + " strings");
    }

    static String join(Collection<Long> addrs) {
        StringBuilder b = new StringBuilder();
        for (Long a : addrs) {
            if (b.length() > 0) {
                b.append(',');
            }
            b.append(String.format("0x%08x", a));
        }
        return b.toString();
    }

    void exportImports() throws IOException {
        int n = 0;
        try (BufferedWriter w = writer("imports.tsv")) {
            w.write("dll\tfunction\tiat\tn_callers\tcallers\n");
            SymbolIterator syms = st.getExternalSymbols();
            List<Symbol> list = new ArrayList<>();
            while (syms.hasNext()) {
                list.add(syms.next());
            }
            for (Symbol s : list) {
                ExternalLocation loc = currentProgram.getExternalManager().getExternalLocation(s);
                if (loc == null) {
                    continue;
                }
                TreeSet<Long> callers = new TreeSet<>();
                TreeSet<Long> iats = new TreeSet<>();
                ArrayDeque<Address> work = new ArrayDeque<>();
                Set<Address> seen = new HashSet<>();
                work.add(s.getAddress());
                // Follow: external <- IAT slot <- instruction, and external <- thunk <- call.
                while (!work.isEmpty()) {
                    Address a = work.poll();
                    if (!seen.add(a)) {
                        continue;
                    }
                    for (Reference r : rm.getReferencesTo(a)) {
                        Address from = r.getFromAddress();
                        Function g = fm.getFunctionContaining(from);
                        if (g == null) {
                            if (from.isMemoryAddress()) {
                                iats.add(from.getOffset());
                                work.add(from);
                            }
                        }
                        else if (g.isThunk()) {
                            work.add(g.getEntryPoint());
                        }
                        else {
                            callers.add(g.getEntryPoint().getOffset());
                        }
                    }
                }
                w.write(loc.getLibraryName() + "\t" + loc.getLabel() + "\t" + join(iats) + "\t"
                    + callers.size() + "\t" + join(callers) + "\n");
                n++;
            }
        }
        println("KOTOR: imports.tsv " + n + " imports");
    }

    // Pointer classes for the table scan.
    static final char F = 'F', C = 'C', S = 'S', D = 'D', Z = '0', I = 'i', X = '-';

    char classify(long v) {
        if (v == 0) {
            return Z;
        }
        if (v < 0x10000) {
            return I;
        }
        if (v > 0xffffffffL || v < 0x400000L) {
            return X;
        }
        Address a = toAddr32(v);
        if (textSet.contains(a)) {
            return fm.getFunctionAt(a) != null ? F : C;
        }
        if (dataSet.contains(a)) {
            return stringAt(a) != null ? S : D;
        }
        return X;
    }

    static boolean isPtr(char c) {
        return c == F || c == C || c == S || c == D;
    }

    String preview(long v, char c) {
        Address a = toAddr32(v);
        switch (c) {
            case F: return fm.getFunctionAt(a).getName(true);
            case S: {
                String s = stringAt(a);
                return "\"" + esc(s.length() > 40 ? s.substring(0, 40) + "..." : s) + "\"";
            }
            case Z: return "0";
            case I: return Long.toString(v);
            default: {
                Symbol s = st.getPrimarySymbol(a);
                return s != null ? s.getName(true) : hex(v);
            }
        }
    }

    TreeSet<Long> refFunctions(Address a) {
        TreeSet<Long> out = new TreeSet<>();
        for (Reference r : rm.getReferencesTo(a)) {
            Function g = fm.getFunctionContaining(r.getFromAddress());
            if (g != null) {
                out.add(g.getEntryPoint().getOffset());
            }
        }
        return out;
    }

    // Runs of pointers in the data sections: function tables, vtables, string tables and arrays
    // of records that hold pointers. A run may hold zeros and small integers (record fields) but
    // never more than three in a row, and starts and ends on a pointer.
    void exportPointerTables() throws Exception {
        int nTables = 0, nVt = 0;
        try (BufferedWriter tw = writer("tables.tsv"); BufferedWriter vw = writer("vtables.tsv")) {
            tw.write("addr\tdwords\tperiod\tpattern\tkind\tn_fn\tn_str\tn_data\tref_functions\t"
                + "referenced_offsets\tpreview\n");
            vw.write("addr\tname\tslots\tref_functions\tentries\n");
            for (MemoryBlock b : mem.getBlocks()) {
                if (b.isExecute() || !b.isInitialized() || b.isExternalBlock()
                    || b.getName().startsWith("Headers") || b.getName().equals(".rsrc")) {
                    continue;
                }
                int len = (int) b.getSize();
                byte[] bytes = new byte[len];
                b.getBytes(b.getStart(), bytes);
                int n = len / 4;
                long[] vals = new long[n];
                char[] cls = new char[n];
                for (int i = 0; i < n; i++) {
                    vals[i] = (bytes[i * 4] & 0xffL) | (bytes[i * 4 + 1] & 0xffL) << 8
                        | (bytes[i * 4 + 2] & 0xffL) << 16 | (bytes[i * 4 + 3] & 0xffL) << 24;
                    cls[i] = classify(vals[i]);
                }
                long base = b.getStart().getOffset();
                int i = 0;
                while (i < n) {
                    if (!isPtr(cls[i])) {
                        i++;
                        continue;
                    }
                    int j = i, last = i, ptrs = 0, gap = 0;
                    while (j < n) {
                        if (isPtr(cls[j])) {
                            last = j;
                            ptrs++;
                            gap = 0;
                        }
                        else if (cls[j] == Z || cls[j] == I) {
                            if (++gap > 3) {
                                break;
                            }
                        }
                        else {
                            break;
                        }
                        j++;
                    }
                    int end = last + 1;
                    if (ptrs >= 4) {
                        writeTable(tw, base, vals, cls, i, end, ptrs);
                        nTables++;
                    }
                    nVt += writeVtables(vw, base, vals, cls, i, end);
                    i = end;
                }
            }
        }
        println("KOTOR: tables.tsv " + nTables + " pointer tables, vtables.tsv " + nVt
            + " vtable candidates");
    }

    void writeTable(BufferedWriter w, long base, long[] vals, char[] cls, int s, int e, int ptrs)
            throws IOException {
        int count = e - s;
        // Smallest period whose class pattern repeats for >= 90% of the entries.
        int period = 1;
        for (int k = 1; k <= 8 && k < count; k++) {
            int same = 0, tot = 0;
            for (int i = s; i + k < e; i++) {
                tot++;
                char a = cls[i] == C ? F : cls[i], c = cls[i + k] == C ? F : cls[i + k];
                if (a == c || (a == I && c == Z) || (a == Z && c == I)) {
                    same++;
                }
            }
            if (tot > 0 && same * 10 >= tot * 9) {
                period = k;
                break;
            }
        }
        StringBuilder pat = new StringBuilder();
        for (int i = s; i < s + period && i < e; i++) {
            pat.append(cls[i]);
        }
        int nf = 0, ns = 0, nd = 0;
        for (int i = s; i < e; i++) {
            if (cls[i] == F || cls[i] == C) {
                nf++;
            }
            else if (cls[i] == S) {
                ns++;
            }
            else if (cls[i] == D) {
                nd++;
            }
        }
        TreeSet<Long> fns = new TreeSet<>();
        List<String> offs = new ArrayList<>();
        for (int i = s; i < e; i++) {
            Address a = toAddr32(base + 4L * i);
            TreeSet<Long> r = refFunctions(a);
            if (!r.isEmpty()) {
                fns.addAll(r);
                if (offs.size() < 12) {
                    offs.add("+" + Integer.toHexString(4 * (i - s)));
                }
            }
        }
        StringBuilder pv = new StringBuilder();
        for (int i = s; i < e && i < s + Math.max(8, period * 2); i++) {
            if (pv.length() > 0) {
                pv.append(" | ");
            }
            pv.append(preview(vals[i], cls[i]));
        }
        List<Long> fl = new ArrayList<>(fns);
        if (fl.size() > 20) {
            fl = fl.subList(0, 20);
        }
        // A guess at what the run is, so the compiler's exception tables can be filtered out.
        String kind;
        boolean codeOnly = pat.toString().replaceAll("[FC]", "").isEmpty();
        if (fns.isEmpty() && period == 2 && pat.length() == 2 && pat.charAt(0) == C
            && (pat.charAt(1) == Z || pat.charAt(1) == I)) {
            kind = "eh_unwind";
        }
        else if (codeOnly && period == 1) {
            kind = fns.isEmpty() ? "code_ptrs" : "fn_table";
        }
        else if (ns * 2 > count) {
            kind = "string_table";
        }
        else if (period > 1) {
            kind = "records";
        }
        else {
            kind = "mixed";
        }
        w.write(hex(base + 4L * s) + "\t" + count + "\t" + period + "\t" + pat + "\t" + kind
            + "\t" + nf + "\t"
            + ns + "\t" + nd + "\t" + join(fl) + (fns.size() > 20 ? ",..." : "") + "\t"
            + String.join(",", offs) + "\t" + pv + "\n");
    }

    // Splits code-pointer runs at every slot that code references: each piece starting at a
    // referenced slot is a vtable candidate (constructors and destructors store its address).
    int writeVtables(BufferedWriter w, long base, long[] vals, char[] cls, int s, int e)
            throws IOException {
        int written = 0;
        int i = s;
        while (i < e) {
            if (!(cls[i] == F || cls[i] == C)) {
                i++;
                continue;
            }
            Address a = toAddr32(base + 4L * i);
            TreeSet<Long> refs = refFunctions(a);
            if (refs.isEmpty()) {
                i++;
                continue;
            }
            int j = i + 1;
            while (j < e && (cls[j] == F || cls[j] == C)
                && refFunctions(toAddr32(base + 4L * j)).isEmpty()) {
                j++;
            }
            if (j - i >= 2) {
                Symbol sym = st.getPrimarySymbol(a);
                String name = sym != null ? sym.getName(true) : "";
                StringBuilder ents = new StringBuilder();
                for (int k = i; k < j; k++) {
                    if (ents.length() > 0) {
                        ents.append(',');
                    }
                    ents.append(hex(vals[k]));
                    if (cls[k] == F) {
                        String fname = fm.getFunctionAt(toAddr32(vals[k])).getName(true);
                        if (!fname.startsWith("FUN_")) {
                            ents.append('=').append(fname);
                        }
                    }
                }
                w.write(hex(a) + "\t" + name + "\t" + (j - i) + "\t" + join(refs) + "\t" + ents
                    + "\n");
                written++;
            }
            i = j;
        }
        return written;
    }

    // Every data address that code references, with the functions that reference it.
    void exportGlobals() throws IOException {
        int n = 0;
        try (BufferedWriter w = writer("globals.tsv")) {
            w.write("addr\tname\ttype\tsection\tn_ref_functions\tref_functions\n");
            AddressIterator it = rm.getReferenceDestinationIterator(dataSet, true);
            while (it.hasNext()) {
                Address a = it.next();
                if (stringAt(a) != null || importAt(a) != null) {
                    continue;
                }
                TreeSet<Long> fns = refFunctions(a);
                if (fns.isEmpty()) {
                    continue;
                }
                Symbol s = st.getPrimarySymbol(a);
                Data d = listing.getDataAt(a);
                String type = d != null ? d.getDataType().getName() : "";
                MemoryBlock b = mem.getBlock(a);
                List<Long> fl = new ArrayList<>(fns);
                if (fl.size() > 40) {
                    fl = fl.subList(0, 40);
                }
                w.write(hex(a) + "\t" + (s != null ? s.getName(true) : "") + "\t" + type + "\t"
                    + (b != null ? b.getName() : "") + "\t" + fns.size() + "\t" + join(fl)
                    + (fns.size() > 40 ? ",..." : "") + "\n");
                n++;
            }
        }
        println("KOTOR: globals.tsv " + n + " referenced globals");
    }

    // The binary was built mostly without RTTI; this lists what Ghidra's RTTI analyzer found.
    void exportRtti() throws IOException {
        try (BufferedWriter w = writer("rtti.tsv")) {
            w.write("class\tsymbol\taddr\n");
            SymbolIterator it = st.getAllSymbols(true);
            while (it.hasNext()) {
                Symbol s = it.next();
                String n = s.getName();
                if (n.equals("vftable") || n.startsWith("RTTI_") || n.contains("vftable")) {
                    w.write(s.getParentNamespace().getName(true) + "\t" + n + "\t"
                        + hex(s.getAddress()) + "\n");
                }
            }
        }
    }

    void exportSegments() throws IOException {
        try (BufferedWriter w = writer("segments.tsv")) {
            w.write("name\tstart\tend\tsize\tperms\tinitialized\n");
            for (MemoryBlock b : mem.getBlocks()) {
                w.write(b.getName() + "\t" + hex(b.getStart()) + "\t" + hex(b.getEnd()) + "\t"
                    + b.getSize() + "\t" + (b.isRead() ? "r" : "-") + (b.isWrite() ? "w" : "-")
                    + (b.isExecute() ? "x" : "-") + "\t" + b.isInitialized() + "\n");
            }
        }
    }

    // ---------------------------------------------------------------- names database

    static class NameRow {
        String addr, name, proto, comment;

        String key() {
            return addr + "\t" + name + "\t" + proto + "\t" + comment;
        }
    }

    static List<NameRow> readNames(Path p) throws IOException {
        List<NameRow> out = new ArrayList<>();
        if (!Files.exists(p)) {
            return out;
        }
        for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
            if (line.isBlank() || line.startsWith("#") || line.startsWith("addr\t")) {
                continue;
            }
            String[] c = line.split("\t", -1);
            NameRow r = new NameRow();
            r.addr = c[0].trim().toLowerCase();
            r.name = c.length > 1 ? c[1].trim() : "";
            r.proto = c.length > 2 ? c[2].trim() : "";
            r.comment = c.length > 3 ? c[3].trim() : "";
            out.add(r);
        }
        return out;
    }

    Namespace namespaceFor(String qualified, boolean asClass) throws Exception {
        int k = qualified.lastIndexOf("::");
        if (k < 0) {
            return currentProgram.getGlobalNamespace();
        }
        Namespace ns = NamespaceUtils.createNamespaceHierarchy(qualified.substring(0, k), null,
            currentProgram, SourceType.USER_DEFINED);
        if (asClass && !(ns instanceof GhidraClass)) {
            ns = NamespaceUtils.convertNamespaceToClass(ns);
        }
        return ns;
    }

    static String baseName(String qualified) {
        int k = qualified.lastIndexOf("::");
        return k < 0 ? qualified : qualified.substring(k + 2);
    }

    static final Pattern TYPE_PTR = Pattern.compile("\\b([A-Za-z_][A-Za-z0-9_]*)\\s*\\*");

    // Prototypes name the engine's classes before anyone has laid them out: make an empty
    // structure for each unknown type used through a pointer so the parser accepts them.
    void declareUnknownTypes(String proto) {
        DataTypeManager dtm = currentProgram.getDataTypeManager();
        Matcher m = TYPE_PTR.matcher(proto);
        while (m.find()) {
            String t = m.group(1);
            if (t.equals("const") || t.equals("struct") || t.equals("unsigned")) {
                continue;
            }
            List<DataType> found = new ArrayList<>();
            dtm.findDataTypes(t, found);
            if (found.isEmpty() && BuiltInDataTypeManager.getDataTypeManager()
                .getDataType(new CategoryPath("/"), t) == null) {
                StructureDataType sdt = new StructureDataType(new CategoryPath("/kotor"), t, 0,
                    dtm);
                dtm.addDataType(sdt, DataTypeConflictHandler.KEEP_HANDLER);
                println("KOTOR: declared empty struct " + t);
            }
        }
    }

    boolean applyPrototype(Function f, String qualified, String proto) {
        try {
            // The parser wants a plain identifier where the name goes.
            String p = proto;
            if (p.contains(qualified)) {
                p = p.replace(qualified, "kotor_fn");
            }
            else {
                p = p.replaceFirst("([A-Za-z_][A-Za-z0-9_:~]*)\\s*\\(", "kotor_fn(");
            }
            // The C parser rejects __thiscall: take the convention out and set it afterwards.
            String cc = null;
            Matcher ccm = Pattern.compile("\\b(__thiscall|__cdecl|__stdcall|__fastcall)\\b")
                .matcher(p);
            if (ccm.find()) {
                cc = ccm.group(1);
                p = p.substring(0, ccm.start()) + p.substring(ccm.end());
            }
            p = p.trim().replaceAll(";$", "");
            declareUnknownTypes(p);
            FunctionDefinitionDataType def;
            try {
                def = CParserUtils.parseSignature((DataTypeManagerService) null, currentProgram,
                    p, false);
            }
            catch (Exception e) {
                println("KOTOR: could not parse prototype for " + qualified + ": " + proto + " ("
                    + e.getMessage().split("\n")[0] + ")");
                return false;
            }
            if (def == null) {
                println("KOTOR: could not parse prototype for " + qualified + ": " + proto);
                return false;
            }
            if (cc != null) {
                def.setCallingConvention(cc);
            }
            // A __thiscall prototype may spell out `this`; Ghidra adds it from the class.
            ParameterDefinition[] ps = def.getArguments();
            if (ps.length > 0 && ps[0].getName().equals("this")
                && "__thiscall".equals(def.getCallingConventionName())) {
                def.setArguments(Arrays.copyOfRange(ps, 1, ps.length));
            }
            ApplyFunctionSignatureCmd cmd = new ApplyFunctionSignatureCmd(f.getEntryPoint(), def,
                SourceType.USER_DEFINED, cc == null, FunctionRenameOption.NO_CHANGE);
            if (!cmd.applyTo(currentProgram, monitor)) {
                println("KOTOR: prototype not applied to " + qualified + ": "
                    + cmd.getStatusMsg());
                return false;
            }
            return true;
        }
        catch (Exception e) {
            println("KOTOR: bad prototype for " + qualified + ": " + proto + " (" + e.getMessage()
                + ")");
            return false;
        }
    }

    void applyNames(Path namesPath, Path statePath, boolean all) throws Exception {
        List<NameRow> rows = readNames(namesPath);
        Set<String> applied = new HashSet<>();
        if (!all) {
            for (NameRow r : readNames(statePath)) {
                applied.add(r.key());
            }
        }
        Set<Function> changedFns = new LinkedHashSet<>();
        Set<Address> changedData = new LinkedHashSet<>();
        int ok = 0, bad = 0, skipped = 0;
        Set<String> failedKeys = new HashSet<>();
        for (NameRow r : rows) {
            if (applied.contains(r.key())) {
                skipped++;
                continue;
            }
            Address a;
            try {
                a = toAddr32(Long.parseLong(r.addr.replaceFirst("^0x", ""), 16));
            }
            catch (NumberFormatException e) {
                println("KOTOR: bad address " + r.addr);
                failedKeys.add(r.key());
                bad++;
                continue;
            }
            try {
                Function f = fm.getFunctionAt(a);
                if (f == null && textSet.contains(a) && listing.getInstructionAt(a) != null
                    && !r.name.isEmpty()) {
                    f = createFunction(a, null);
                    if (f != null) {
                        println("KOTOR: created function at " + hex(a));
                    }
                }
                if (f != null) {
                    if (!r.name.isEmpty() && !r.name.equals(f.getName(true))) {
                        Namespace ns = namespaceFor(r.name, true);
                        f.setParentNamespace(ns);
                        f.setName(baseName(r.name), SourceType.USER_DEFINED);
                    }
                    if (!r.proto.isEmpty() && !applyPrototype(f,
                        r.name.isEmpty() ? f.getName(true) : r.name, r.proto)) {
                        failedKeys.add(r.key());
                        bad++;
                    }
                    if (!r.comment.isEmpty()) {
                        f.setComment(r.comment.replace("\\n", "\n"));
                    }
                    changedFns.add(f);
                }
                else {
                    if (!r.name.isEmpty()) {
                        Namespace ns = namespaceFor(r.name, false);
                        Symbol s = st.createLabel(a, baseName(r.name), ns, SourceType.USER_DEFINED);
                        s.setPrimary();
                    }
                    if (!r.proto.isEmpty()) {
                        DataTypeParser parser = new DataTypeParser(
                            currentProgram.getDataTypeManager(), null, null,
                            DataTypeParser.AllowedDataTypes.ALL);
                        declareUnknownTypes(r.proto + " *");
                        DataType dt = parser.parse(r.proto);
                        clearListing(a, a.add(Math.max(dt.getLength(), 1) - 1));
                        createData(a, dt);
                    }
                    if (!r.comment.isEmpty()) {
                        listing.setComment(a, CommentType.PLATE, r.comment.replace("\\n", "\n"));
                    }
                    changedData.add(a);
                }
                ok++;
            }
            catch (Exception e) {
                println("KOTOR: failed " + r.addr + " " + r.name + ": " + e);
                failedKeys.add(r.key());
                bad++;
            }
        }
        println("KOTOR: names applied " + ok + ", problems " + bad + ", unchanged " + skipped);

        // Re-export what shows the new names: the functions themselves, their callers (call
        // sites), their callees (caller lists in headers) and readers of renamed globals.
        LinkedHashSet<Function> affected = new LinkedHashSet<>(changedFns);
        for (Function f : changedFns) {
            Info in = info(f);
            for (Long c : in.callers.keySet()) {
                affected.add(fm.getFunctionAt(toAddr32(c)));
            }
            for (Long c : in.callees.keySet()) {
                affected.add(fm.getFunctionAt(toAddr32(c)));
            }
            for (Long c : in.ptrRefs.keySet()) {
                Function g = fm.getFunctionContaining(toAddr32(c));
                if (g != null) {
                    affected.add(g);
                }
            }
        }
        for (Address a : changedData) {
            for (Long c : refFunctions(a)) {
                affected.add(fm.getFunctionAt(toAddr32(c)));
            }
        }
        affected.remove(null);
        println("KOTOR: re-exporting " + affected.size() + " affected functions");
        decompileSome(affected);
        if (!changedData.isEmpty() || !changedFns.isEmpty()) {
            exportTables();
        }
        // Remember what is applied so the next run only does new or edited rows.
        Files.createDirectories(statePath.getParent());
        try (BufferedWriter w = Files.newBufferedWriter(statePath, StandardCharsets.UTF_8)) {
            w.write("addr\tname\tprototype\tcomment\n");
            // Failed rows stay out, so the next run retries them.
            for (NameRow r : rows) {
                if (!failedKeys.contains(r.key())) {
                    w.write(r.key() + "\n");
                }
            }
        }
    }
}
