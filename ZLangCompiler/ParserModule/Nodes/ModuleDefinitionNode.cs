using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ModuleDefinitionNode : AstNode
{
    public required QualifiedIdentifierExpressionNode Name { get; init; }
    public required ModuleLevelStatementNode[] Body { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitModuleDefinition(this);
    }
}