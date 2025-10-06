namespace ParserModule.Nodes;

public class PrimaryExpressionNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitPrimaryExpressionNode(this);
    }
}