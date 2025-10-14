using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ProgramDefinitionNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitProgram(this);
    }

    public required List<AstNode> Functions { get; init; }
    
    public List<TopLevelStatementNode> Statements { get; init; }
}