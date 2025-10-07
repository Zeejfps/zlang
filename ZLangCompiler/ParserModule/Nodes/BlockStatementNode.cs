namespace ParserModule.Nodes;

public sealed class BlockStatementNode : AstNode
{
    public IReadOnlyCollection<AstNode> Statements { get; }

    public BlockStatementNode()
    {
        
    }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitBlockStatement(this);
    }
}