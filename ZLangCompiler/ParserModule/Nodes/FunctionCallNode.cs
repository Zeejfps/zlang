using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public class FunctionCallNode : StatementNode
{
    public required QualifiedIdentifierExpressionNode Identifier { get; init; }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitFunctionCall(this);
    }
}