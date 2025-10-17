using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public class FunctionCallNode : ExpressionNode
{
    public required QualifiedIdentifierExpressionNode Identifier { get; init; }
    public List<ExpressionNode>? Arguments { get; set; }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitFunctionCall(this);
    }
}