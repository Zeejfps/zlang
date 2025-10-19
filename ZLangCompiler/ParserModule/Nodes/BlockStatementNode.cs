using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class BlockStatementNode : StatementNode
{
    public List<StatementNode> Statements { get; }

    public BlockStatementNode(List<StatementNode> statements)
    {
        Statements = statements;
    }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitBlockStatement(this);
    }
}