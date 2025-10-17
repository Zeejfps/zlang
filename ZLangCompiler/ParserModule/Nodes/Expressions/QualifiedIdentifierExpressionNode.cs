using ParserModule.Visitors;

namespace ParserModule.Nodes.Expressions;

public sealed class QualifiedIdentifierExpressionNode : ExpressionNode
{
    public required List<string> Parts { get; init; }
    
    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitQualifiedIdentifier(this);
    }

    public override string ToString()
    {
        return string.Join(".", Parts);
    }
}