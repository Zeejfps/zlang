namespace ParserModule.Nodes;

public sealed class ModuleDefinitionNode : AstNode
{
    public required QualifiedIdentifierExpressionNode Name { get; init; }
    public required BlockStatementNode Body { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitModuleDefinitionNode(this);
    }
}