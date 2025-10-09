namespace ParserModule.Nodes;

public sealed class BlockStatementNode : StatementNode
{
    public IReadOnlyList<AstNode> Statements { get; }

    public BlockStatementNode(List<AstNode> statements)
    {
        Statements = statements;
    }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitBlockStatement(this);
    }
}