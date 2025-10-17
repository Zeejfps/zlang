using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ExpressionStatement : StatementNode
{
    public required ExpressionNode Expression { get; init; }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitExpressionStatement(this);
    }
}