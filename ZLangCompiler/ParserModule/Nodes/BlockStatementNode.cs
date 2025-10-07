namespace ParserModule.Nodes;

public sealed class BlockStatementNode : AstNode
{
    public IReadOnlyCollection<AstNode> Statements { get; }

    public BlockStatementNode(List<AstNode> statements)
    {
        Statements = statements;
    }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitBlockStatement(this);
    }
}