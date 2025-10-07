namespace ParserModule.Nodes;

public sealed class FunctionDeclarationNode : AstNode
{
    public required string Name { get; init; }
    public required BlockStatementNode Body { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitFunctionDeclarationNode(this);
    }
}