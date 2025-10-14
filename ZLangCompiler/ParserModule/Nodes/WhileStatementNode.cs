using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class WhileStatementNode : StatementNode
{
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitWhileStatement(this);
    }
    
    public required ExpressionNode Condition { get; init; }
    public required StatementNode Body { get; init; }
}