namespace ParserModule.Nodes;

public sealed class ModuleDefinitionNode : AstNode
{
    public required List<AstNode> Functions { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitModuleDefinitionNode(this);
    }
}