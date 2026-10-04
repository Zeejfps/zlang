// Pre-script for the first import of swkotor.exe: turns on the analyzers that make the
// decompiler's output better at the cost of a longer first analysis, and turns off one that
// damages the listing.
// @category KOTOR

import ghidra.app.script.GhidraScript;

public class SetAnalysisOptions extends GhidraScript {
    @Override
    protected void run() throws Exception {
        // Commits parameter counts and __thiscall to function signatures, so callers decompile
        // with the right arguments instead of in_ECX / extraout guesses.
        setAnalysisOption(currentProgram, "Decompiler Parameter ID", "true");
        // This analyzer flagged CExoString::~CExoString (33 bytes, ends in RET) and four other
        // functions that return as never returning, and then "repaired flow damage" by clearing
        // the code after every call to them: a fifth of .text was never disassembled, 420 of our
        // named functions did not exist, and every caller decompiled without its tail. The few
        // functions that truly never return are found by "Non-Returning Functions - Known" (by
        // name: exit, abort) or carry `__noreturn` in names.tsv. See docs/re/noreturn-fix.md.
        setAnalysisOption(currentProgram, "Non-Returning Functions - Discovered", "false");
        println("KOTOR: analysis options set");
    }
}
