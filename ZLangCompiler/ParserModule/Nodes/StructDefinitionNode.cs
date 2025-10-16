using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class StructDefinitionNode : ModuleLevelStatementNode
{
    public required string Name { get; init; }
    public required List<StructFieldDeclarationNode> Properties { get; init; }

    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitStructDefinition(this);
    }
}

public sealed class StructFieldDeclarationNode
{
    public required string Name { get; init; }
    public required TypeNode Type { get; init; }
}