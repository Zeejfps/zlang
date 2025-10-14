namespace ParserModule.Nodes;

public sealed class VarDefinitionStatementNode : StatementNode
{
    public required string Name { get; init; }
    public AstNode? Type { get; init; }
    public required ExpressionNode Value { get; init; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitVarDefinition(this);
    }
}