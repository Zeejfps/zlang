using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class VarDefinitionStatementNode : StatementNode
{
    public required string Identifier { get; init; }
    public TypeNode? Type { get; init; }
    public required ExpressionNode Value { get; init; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitVarDefinition(this);
    }
}