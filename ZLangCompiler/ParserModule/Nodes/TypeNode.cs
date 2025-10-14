using ParserModule.Visitors;

namespace ParserModule.Nodes;

public abstract class TypeNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        Accept(visitor);
    }

    public abstract void Accept(ITypeNodeVisitor visitor);
}