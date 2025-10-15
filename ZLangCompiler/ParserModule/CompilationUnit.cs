using ParserModule.Nodes;

namespace ParserModule;

public sealed class CompilationUnit
{
    public required List<TopLevelStatementNode> Statements { get; init; }
}