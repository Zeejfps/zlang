using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ImportStatementNode : TopLevelStatementNode
{
    public required string AliasName { get; init; }
    public required QualifiedIdentifierExpressionNode QualifiedIdentifier { get; init; }

    public override void Accept(ITopLevelStatementVisitor visitor)
    {
        visitor.VisitStructImport(this);
    }
}