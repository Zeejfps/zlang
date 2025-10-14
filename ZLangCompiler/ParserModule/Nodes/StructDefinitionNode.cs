using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class StructDefinitionNode : ModuleLevelStatementNode
{
    public required string Name { get; init; }
    
    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitStructDefinition(this);
    }
}