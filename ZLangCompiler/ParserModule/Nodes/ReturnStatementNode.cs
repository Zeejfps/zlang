using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ReturnStatementNode : StatementNode
{
    public ExpressionNode? Result { get; init; }
    public TypeNode? InferredType { get; set; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitReturnStatementNode(this);
    }
}