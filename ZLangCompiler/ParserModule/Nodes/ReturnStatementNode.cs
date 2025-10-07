namespace ParserModule.Nodes;

public sealed class ReturnStatementNode : AstNode
{
    public AstNode? Value { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitReturnStatementNode(this);
    }
}