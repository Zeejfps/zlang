using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class StructDefinitionNode : ModuleLevelStatementNode
{
    public required string Name { get; init; }
    public required List<StructPropertyDeclarationNode> Properties { get; init; }

    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitStructDefinition(this);
    }
}

public sealed class StructPropertyDeclarationNode
{
    public required string Name { get; init; }
    public required TypeNode Type { get; init; }
}