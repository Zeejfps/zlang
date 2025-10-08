namespace ParserModule.Nodes;

public sealed class StructDefinitionNode : AstNode
{
    public required string Name { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitStructDefinitionNode(this);
    }
}