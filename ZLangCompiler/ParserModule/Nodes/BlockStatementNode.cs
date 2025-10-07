namespace ParserModule.Nodes;

public sealed class BlockStatementNode : AstNode
{
    public IReadOnlyList<AstNode> Statements { get; }

    public BlockStatementNode(List<AstNode> statements)
    {
        Statements = statements;
    }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitBlockStatement(this);
    }
}