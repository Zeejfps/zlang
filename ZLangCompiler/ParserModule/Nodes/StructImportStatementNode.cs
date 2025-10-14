using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class StructImportStatementNode : AstNode
{
    public required string AliasName { get; init; }
    public required QualifiedIdentifierExpressionNode QualifiedIdentifier { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitStructImportStatementNode(this);
    }
}