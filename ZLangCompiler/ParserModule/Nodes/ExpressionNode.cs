namespace ParserModule.Nodes;

public abstract class ExpressionNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        Accept(visitor);
    }
    
    public abstract void Accept(IExpressionNodeVisitor visitor);
}