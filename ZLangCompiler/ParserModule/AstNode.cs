using ParserModule.Visitors;

namespace ParserModule;

public abstract class AstNode
{
    public abstract void Accept(IAstNodeVisitor visitor);
}