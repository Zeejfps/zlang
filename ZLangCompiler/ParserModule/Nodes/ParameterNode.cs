namespace ParserModule.Nodes;

public sealed class ParameterNode : AstNode
{
    public required string Name { get; init; }
    public required AstNode Type { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitParameterNode(this);
    }
}