namespace ParserModule.Nodes;

public sealed class ReturnStatementNode : StatementNode
{
    public AstNode? Value { get; init; }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitReturnStatementNode(this);
    }
}