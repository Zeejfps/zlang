using System.Text.Json.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ModuleDefinitionNode : TopLevelStatementNode
{
    public required QualifiedIdentifierExpressionNode Name { get; init; }
    public required ModuleLevelStatementNode[] Body { get; init; }
    public required JsonObject Metadata { get; init; }

    public override void Accept(ITopLevelStatementVisitor visitor)
    {
        visitor.VisitModuleDefinition(this);
    }
}