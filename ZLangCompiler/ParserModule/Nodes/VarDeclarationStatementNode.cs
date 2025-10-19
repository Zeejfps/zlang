using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class VarDeclarationStatementNode : StatementNode
{
    public required string Identifier { get; init; }
    public TypeNode? Type { get; init; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitVarDeclaration(this);
    }
}